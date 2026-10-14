"""Fresh-page setup, pre-freeze audit and conservative routing; zero paid API calls."""
from copy import deepcopy
import io
import json
import os
from pathlib import Path
from unittest.mock import patch
import unittest

from agent.contracts import validate_plan, test_steps, write_bundle
from agent.diagnostics import route_failure
from agent.plan_review import inspect_plan, validate_audit, failure_fingerprint
from agent.planning import validate_recovery
from agent.provider import ChatClient, ProviderError
from agent.quality import review_plan
from agent.runner import run
from agent.trace import Trace
from agent.verification import verify
from test_mvp import TempTest, FakeClient, config, example_plan, example_bundle, verifier_result


def dependent_plan():
    plan = example_plan()
    first = plan['tests'][0]
    first['purpose'] = 'initial'
    second = deepcopy(first)
    second['id'] = 'T2'
    second['purpose'] = 'legal_action'
    second['steps'][0]['value'] = 1
    second['steps'][-1]['value'] = 2
    plan['tests'].append(second)
    return plan


def corrected_plan():
    plan = dependent_plan()
    plan['tests'][1]['setup_steps'] = [{'action': 'click', 'selector': '#increment'}]
    return plan


def revised_audit():
    return {'status': 'revised', 'reason': 'Repeat prerequisites on the new page',
            'issues': [{'test_id': 'T2', 'reason': 'Missing local purchase/input setup',
                        'spec_evidence': 'Counter starts at zero and increments once per click.'}],
            'plan': corrected_plan()}


def actual_failure(plan, tid='T1'):
    result = verifier_result(False)
    result['tests'] = [{'id': t['id'], 'passed': t['id'] != tid} for t in plan['tests']]
    failed = next(t for t in result['tests'] if t['id'] == tid)
    failed.update(failed_step=1, failure_kind='assertion_mismatch', observations=[
        {'actual': 0, 'expected': 1, 'op': 'eq', 'passed': False}])
    return result


class SetupContractTests(unittest.TestCase):
    def test_setup_and_check_share_capture_scope(self):
        plan = example_plan()
        plan['tests'][0]['setup_steps'] = [{'action': 'capture', 'name': 'initial'}]
        plan['tests'][0]['steps'][-1] = {'action': 'assert', 'source': 'state', 'path': 'score',
                                      'op': 'gt', 'value_from': {'capture': 'initial', 'path': 'score'}}
        self.assertEqual(len(test_steps(validate_plan(plan)['tests'][0])), 4)

    def test_setup_cannot_exceed_combined_step_limit(self):
        plan = example_plan()
        plan['tests'][0]['setup_steps'] = [{'action': 'wait', 'ms': 0}] * 16
        with self.assertRaisesRegex(ValueError, 'Setup and check'):
            validate_plan(plan)

    def test_wait_budget_includes_all_setup_steps(self):
        plan = example_plan()
        plan['tests'][0]['setup_steps'] = [{'action': 'wait', 'ms': 2000}] * 15
        second = deepcopy(plan['tests'][0])
        second['id'] = 'T2'
        plan['tests'].append(second)
        with self.assertRaisesRegex(ValueError, '45 seconds'):
            validate_plan(plan)

    def test_setup_cannot_inject_state(self):
        plan = example_plan()
        plan['tests'][0]['setup_steps'] = [{'action': 'set_state', 'score': 1}]
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            validate_plan(plan)

    def test_assertion_only_in_setup_is_not_acceptance(self):
        plan = example_plan()
        plan['tests'][0]['setup_steps'] = [plan['tests'][0]['steps'][0]]
        plan['tests'][0]['steps'] = [{'action': 'click', 'selector': '#increment'}]
        with self.assertRaisesRegex(ValueError, 'not only setup'):
            validate_plan(plan)

    def test_setup_input_then_check_counts_as_functional_evidence(self):
        plan = example_plan()
        plan['tests'][0]['setup_steps'] = [{'action': 'click', 'selector': '#increment'}]
        plan['tests'][0]['steps'] = [plan['tests'][0]['steps'][-1]]
        self.assertEqual(review_plan(validate_plan(plan))['functional_test_ids'], ['T1'])

    def test_recovery_cannot_change_a_frozen_setup_assertion(self):
        plan = example_plan()
        plan['tests'][0]['setup_steps'] = [{'action': 'assert', 'source': 'state', 'path': 'score', 'op': 'eq', 'value': 0}]
        changed = deepcopy(plan)
        changed['tests'][0]['setup_steps'][0]['value'] = 99
        with self.assertRaisesRegex(ValueError, 'assertion'):
            validate_recovery(plan, changed)


class DraftReviewTests(unittest.TestCase):
    def test_detects_cross_test_state_assumption_without_mutation(self):
        plan = dependent_plan()
        original = deepcopy(plan)
        self.assertEqual([w['test_id'] for w in inspect_plan(plan)['warnings']], ['T2'])
        self.assertEqual(plan, original)

    def test_local_setup_removes_the_initial_state_conflict(self):
        self.assertEqual(inspect_plan(corrected_plan())['warnings'], [])

    def test_review_cannot_solve_an_arbitrary_map(self):
        plan = example_plan()
        plan['title'] = 'Grid with unknown rules'
        self.assertEqual(inspect_plan(plan)['warnings'], [])
        self.assertIn('cannot solve', inspect_plan(plan)['note'])

    def test_prefreeze_revision_preserves_commitments(self):
        plan, review = validate_audit(revised_audit(), validate_plan(dependent_plan()))
        self.assertEqual(plan['requirements'], dependent_plan()['requirements'])
        self.assertEqual(review['status'], 'revised')

    def test_cannot_drop_requirements_or_demote_verification(self):
        for change in ('drop', 'demote', 'contract', 'test_id', 'coverage'):
            value = revised_audit()
            if change == 'drop': value['plan']['requirements'] = []
            if change == 'demote': value['plan']['requirements'][0]['priority'] = 'visual'
            if change == 'contract': value['plan']['state_contract']['extra'] = 'number'
            if change == 'test_id': value['plan']['tests'][1]['id'] = 'Other'
            if change == 'coverage': value['plan']['tests'][1]['requirement_ids'] = ['R1', 'R1']
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_audit(value, validate_plan(dependent_plan()))

    def test_cannot_edit_an_uncited_test(self):
        value = revised_audit()
        value['issues'][0]['test_id'] = 'T1'
        with self.assertRaisesRegex(ValueError, 'specific issue'):
            validate_audit(value, validate_plan(dependent_plan()))

    def test_audit_cannot_remove_assertions_or_change_their_operators(self):
        for weaken in ('remove', 'operator'):
            value = revised_audit()
            if weaken == 'remove': value['plan']['tests'][1]['steps'].pop(0)
            else: value['plan']['tests'][1]['steps'][0]['op'] = 'ne'
            with self.subTest(weaken=weaken), self.assertRaisesRegex(ValueError, 'assertions'):
                validate_audit(value, validate_plan(dependent_plan()))

    def test_approved_cannot_supply_a_replacement_plan(self):
        with self.assertRaises(ValueError):
            validate_audit({'status': 'approved', 'reason': 'OK', 'issues': [], 'plan': example_plan()}, example_plan())

    def test_unverified_is_not_a_revision(self):
        plan, value = validate_audit({'status': 'unverified', 'reason': 'Rules uncertain', 'issues': []}, example_plan())
        self.assertEqual(plan, example_plan())
        self.assertEqual(value['status'], 'unverified')

    def test_malformed_audit_is_rejected(self):
        for status in ({}, [], None, 'passed'):
            with self.subTest(status=status), self.assertRaises(ValueError):
                validate_audit({'status': status, 'reason': 'x', 'issues': []}, example_plan())

    def test_repeated_fingerprint_requires_actual_assertion_evidence(self):
        result = actual_failure(example_plan())
        self.assertEqual(failure_fingerprint(result), failure_fingerprint(deepcopy(result)))
        result['tests'][0]['observations'][-1]['actual'] = 2
        self.assertNotEqual(failure_fingerprint(result), failure_fingerprint(actual_failure(example_plan())))
        self.assertIsNone(failure_fingerprint(verifier_result(False)))

    def test_runtime_failure_is_not_treated_as_a_plan_problem(self):
        result = actual_failure(dependent_plan(), 'T2')
        result['runtime_errors'] = [{'error': 'ReferenceError'}]
        self.assertEqual(route_failure(result, inspect_plan(dependent_plan()))['action'], 'repair_code')
        self.assertIsNone(failure_fingerprint(result))

    def test_conflict_signal_requires_an_actual_failed_test(self):
        result = {'ok': True, 'tests': [{'id': 'T2', 'passed': True}]}
        self.assertEqual(route_failure(result, inspect_plan(dependent_plan()))['action'], 'complete')


class ReviewControllerTests(TempTest):
    def execute(self, draft=None, audit=None, failed=False, **options):
        draft = draft or example_plan()
        calls = []
        class Client(FakeClient):
            def ask_json(self, stage, system, prompt):
                self.calls += 1
                calls.append((stage, json.loads(prompt)))
                if stage == 'plan': return deepcopy(draft)
                if stage == 'plan_audit': return deepcopy(audit)
                if stage == 'diagnose': return {'category': 'uncertain', 'reason': 'No causal evidence', 'evidence_test_ids': ['T1']}
                return example_bundle(extra='/* round ' + str(self.calls) + ' */')
        def verifier(game, plan_path, evidence, **kw):
            plan = json.loads(plan_path.read_text(encoding='utf-8'))
            if failed: return actual_failure(plan, 'T2' if len(plan['tests']) == 2 else 'T1')
            result = verifier_result(True)
            result['tests'] = [{'id': t['id'], 'passed': True} for t in plan['tests']]
            return result
        spec = self.root / 'spec.md'
        spec.write_text('Counter starts at zero and increments once per click.', encoding='utf-8')
        output = self.root / 'run'
        code = run(config(), spec, output, client_factory=Client, verifier=verifier,
                   preflight_fn=lambda **kw: {'ok': True}, **options)
        return code, json.loads((output / 'summary.json').read_text(encoding='utf-8')), calls, output

    def test_prefreeze_audit_sees_no_code_and_freezes_revised_plan(self):
        code, summary, calls, output = self.execute(dependent_plan(), revised_audit(), plan_audit=True)
        self.assertEqual(code, 0)
        self.assertEqual([s for s, _ in calls], ['plan', 'plan_audit', 'code_1'])
        self.assertEqual(set(calls[1][1]), {'original_spec', 'draft_plan', 'execution_contract', 'deterministic_review'})
        self.assertEqual(summary['plan_audit_status'], 'revised')
        frozen = json.loads((output / 'traces/plan.json').read_text(encoding='utf-8'))
        self.assertEqual(frozen, validate_plan(corrected_plan()))
        self.assertTrue((output / 'traces/draft_plan.json').exists())

    def test_unverified_audit_stops_before_game_generation(self):
        code, summary, calls, output = self.execute(audit={'status': 'unverified', 'reason': 'Cannot resolve', 'issues': []}, plan_audit=True)
        self.assertEqual(code, 2)
        self.assertEqual(summary['status'], 'plan_review_required')
        self.assertFalse((output / 'game').exists())
        self.assertEqual(len(calls), 2)

    def test_invalid_audit_cannot_silently_replace_the_plan(self):
        value = revised_audit()
        value['plan']['requirements'][0]['priority'] = 'visual'
        code, summary, calls, output = self.execute(dependent_plan(), value, plan_audit=True)
        self.assertEqual(summary['plan_audit_status'], 'unverified')
        self.assertFalse((output / 'traces/plan.json').exists())
        self.assertEqual(code, 2)

    def test_audit_is_skipped_when_it_would_consume_generation_reserve(self):
        code, summary, calls, _ = self.execute(plan_audit=True, max_calls=2)
        self.assertEqual(code, 0)
        self.assertEqual(summary['plan_audit_status'], 'skipped_budget')
        self.assertEqual([s for s, _ in calls], ['plan', 'code_1'])

    def test_failed_fresh_page_conflict_preserves_game_without_repairing_it(self):
        code, summary, calls, output = self.execute(dependent_plan(), failed=True, max_rounds=5)
        self.assertEqual(summary['status'], 'plan_review_required')
        self.assertEqual([s for s, _ in calls], ['plan', 'code_1'])
        self.assertTrue((output / 'game/index.html').exists())
        self.assertFalse(summary['automated_checks_passed'])
        self.assertEqual(code, 2)

    def test_identical_assertions_stop_after_one_ineffective_repair(self):
        code, summary, calls, _ = self.execute(failed=True, max_rounds=5)
        self.assertEqual(summary['status'], 'plan_review_required')
        self.assertEqual([s for s, _ in calls], ['plan', 'code_1', 'code_2'])
        self.assertEqual(code, 2)

    def test_uncertain_diagnosis_does_not_authorize_more_game_edits(self):
        code, summary, calls, _ = self.execute(failed=True, diagnose_failures=True)
        self.assertEqual(summary['status'], 'plan_review_required')
        self.assertEqual([s for s, _ in calls], ['plan', 'code_1', 'diagnose'])
        self.assertEqual(code, 2)

    def test_audit_off_by_default_changes_no_call_count(self):
        code, summary, calls, _ = self.execute()
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 2)
        self.assertEqual(summary['plan_audit_status'], 'not_requested')

    def test_provider_audit_has_one_attempt_even_on_bad_json(self):
        import time
        client = ChatClient(config(), Trace(self.root / 'trace'), 8, time.monotonic() + 30)
        response = {'choices': [{'message': {'content': 'not JSON'}}]}
        with patch('agent.provider.open_request', return_value=io.BytesIO(json.dumps(response).encode())), \
             patch('agent.provider.time.sleep'), self.assertRaises(ProviderError):
            client.ask_json('plan_audit', 'review', '{}')
        self.assertEqual(client.calls, 1)


@unittest.skipUnless(os.getenv('MVP_BROWSER_TESTS') == '1', 'Opt-in real browser; zero API calls')
class PlanSetupBrowserTests(TempTest):
    def test_prefreeze_review_to_real_browser_completion(self):
        class Client(FakeClient):
            def ask_json(self, stage, system, prompt):
                self.calls += 1
                if stage == 'plan': return dependent_plan()
                if stage == 'plan_audit': return revised_audit()
                return example_bundle()
        spec = self.root / 'spec.md'
        spec.write_text('Counter starts at zero and increments once per click.', encoding='utf-8')
        output = self.root / 'run'
        code = run(config(), spec, output, client_factory=Client, plan_audit=True)
        summary = json.loads((output / 'summary.json').read_text(encoding='utf-8'))
        self.assertEqual(code, 0, summary)
        self.assertEqual(summary['usage']['api_attempts'], 3)
        self.assertEqual(summary['plan_audit_status'], 'revised')
        self.assertEqual(summary['plan_review']['warnings'], [])

    def test_actual_fresh_page_failure_preserves_artifact_without_code_repair(self):
        class Client(FakeClient):
            def ask_json(self, stage, system, prompt):
                self.calls += 1
                return dependent_plan() if stage == 'plan' else example_bundle()
        spec = self.root / 'spec.md'
        spec.write_text('Counter starts at zero and increments once per click.', encoding='utf-8')
        output = self.root / 'run'
        code = run(config(), spec, output, client_factory=Client, max_rounds=5)
        summary = json.loads((output / 'summary.json').read_text(encoding='utf-8'))
        self.assertEqual(code, 2)
        self.assertEqual(summary['status'], 'plan_review_required')
        self.assertEqual(summary['usage']['api_attempts'], 2)
        self.assertTrue((output / 'game/index.html').exists())

    def browser_check(self, plan, working=True):
        game = self.root / 'game'
        write_bundle(example_bundle(working), game)
        path = self.root / 'plan.json'
        path.write_text(json.dumps(validate_plan(plan)), encoding='utf-8')
        return verify(game, path, self.root / 'evidence', timeout=40)

    def test_missing_setup_does_not_inherit_previous_page_state(self):
        result = self.browser_check(dependent_plan())
        self.assertTrue(result['tests'][0]['passed'])
        self.assertFalse(result['tests'][1]['passed'])
        self.assertEqual(result['tests'][1]['observations'][0]['actual'], 0)

    def test_explicit_setup_reaches_target_with_real_input(self):
        result = self.browser_check(corrected_plan())
        self.assertTrue(result['ok'], result)
        actions = result['tests'][1]['actions']
        self.assertEqual(actions[0]['stage'], 'setup')
        self.assertEqual(actions[1]['stage'], 'check')

    def test_wrong_game_logic_still_fails_with_explicit_setup(self):
        result = self.browser_check(corrected_plan(), working=False)
        self.assertFalse(result['ok'])
        self.assertFalse(result['tests'][1]['passed'])

    def test_setup_capture_uses_same_page_but_not_other_tests(self):
        plan = example_plan()
        plan['tests'][0]['setup_steps'] = [{'action': 'capture', 'name': 'before'}]
        plan['tests'][0]['steps'][-1] = {'action': 'assert', 'source': 'state', 'path': 'score',
                                      'op': 'gt', 'value_from': {'capture': 'before', 'path': 'score'}}
        self.assertTrue(self.browser_check(plan)['ok'])
