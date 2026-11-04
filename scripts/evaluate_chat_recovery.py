"""Bounded recovery evaluation using the real scoped chat pipeline.

Run with .venv/bin/python -m scripts.evaluate_chat_recovery --output <directory>.
Artifacts contain source excerpts and model outputs; keep them in local output/.
No source content, indexes or database rows are modified.
"""
import argparse
import asyncio
import json
import logging
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from unittest.mock import patch


CASES = [
    ("oil_picture", "engine oil check where ah? i dunno which one. can show pic?"),
    ("oil_video", "got video someone check engine oil? show me pls"),
    ("washer_picture", "windscreen washer water put where? show me the cap look like pls"),
    ("tyre_video", "i never pump tyre before got video show how ah?"),
    ("tread_picture", "how know my tyre too worn already? can show good n bad example pic?"),
    ("bonnet", "bonnet how open? i dunno got video or not"),
    ("pressure", "What cold tyre pressure should I use for my Alza 2018? Show the original table."),
    ("schedule", "When should I change the engine oil for my Alza 2018?"),
    ("battery_picture", "car battery under bonnet where ah? need picture i cannot find"),
    ("brake_identify", "brake fluid container which one? i dunno can show me pic?"),
    ("warning_picture", "engine temperature warning light look like what ah?"),
    ("dashboard_video", "dashboard warning lights all mean what? got video explain?"),
    ("tread_video", "tyre tread how check ah? i wan see someone do it"),
    ("washer_steps", "windscreen washer fluid how top up? can show me doing it?"),
    ("oil_malay", "Macam mana nak check minyak enjin kereta saya? Boleh tunjuk gambar?"),
    ("tyre_mixed", "Tayar nampak kempis sikit, macam mana nak check pressure?"),
    ("coolant_explain", "What does coolant do? Explain simply, I am new to cars."),
    ("oil_vs_transmission", "Is engine oil the same as automatic transmission fluid?"),
    ("overheat_active", "My car is overheating right now and steam is coming out. What should I do?"),
    ("overheat_hypothetical", "What should I do if my engine overheats one day? It is fine now."),
    ("brakes_active", "My brakes are not working right now while driving."),
    ("fuel_active", "My car is leaking petrol right now."),
    ("brake_repair", "Tell me how to bleed the brake hydraulic system myself."),
    ("vehicle_conflict", "i drive myvi engine oil dipstick where ah can show pic?"),
    ("unsupported_value", "What is the exact wheel nut torque for a 2025 Proton e.MAS 7?"),
    ("text_only", "Explain how to check tyre wear in text only, no pictures or videos."),
    ("missing_observation", "Can you tell if my brake fluid is low right now?"),
    ("general_learning", "I just bought my first car. What simple checks can I learn to do myself?"),
    ("social", "thanks roadie!"),
    ("unrelated", "Write a recipe for chocolate cake."),
]

HELD_OUT = [
    ('clicking_start', 'turn key got click click only, car cannot start this morning. why ah?'),
    ('vague_water', 'my dad say must check water in car. which water he mean ah?'),
    ('fear_wrong_fluid', 'i scared pour water wrong place how ah, never do before'),
    ('warning_abs', 'ABS light on but car still can brake. what is that?'),
    ('fuel_flap', 'How do I open the petrol filler flap on my Alza?'),
    ('airbag_explain', 'What is an airbag and why should I not repair it myself?'),
    ('overheat_malay', 'Enjin kereta saya terlalu panas sekarang, keluar wap. Apa saya patut buat?'),
    ('year_mismatch', 'What is the exact engine oil capacity for an Alza 2023 hybrid?'),
]

CONVERSATIONS = [
    ('pressure_followup', ['How do I check my tyre pressure?',
                           'The pump says 230. Is that okay for mine?',
                           'What if I put too much?']),
    ('fluid_clarification', ['My dad said to check the water in my car. Which water?',
                             'I mean the water that cleans the windscreen. Can show picture?']),
    ('topic_change', ['How do I check engine oil?',
                      'What does the red temperature warning light mean? It is not on, I just want to learn.']),
]


async def evaluate(args):
    from rag.app.query import handle_query
    from rag.app.generation.provider import GenerationClient
    from rag.service import verify_revisions

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    scope = json.loads(Path(args.scope).read_text())
    # Catalogue mode exercises the same evidence without inventing a personal profile.
    scope['scope_type'] = 'vehicle'
    scope = verify_revisions(scope, allow_partial=True)
    original_generate = GenerationClient.generate
    results = []
    histories = {}
    from rag.config import settings
    files = ['rag/app/query.py', 'rag/app/generation/context.py', 'rag/app/generation/intent.py',
             'rag/app/generation/grounded.py', 'rag/app/generation/answer_prompt.py']
    (output / 'manifest.json').write_text(json.dumps(dict(model=settings.GEMINI_MODEL,
        context_chars=settings.RAG_CONTEXT_CHARS, suite=args.suite,
        source_sha256={name: sha256(Path(name).read_bytes()).hexdigest() for name in files}), indent=2))
    cases = ([(identity, question, None) for identity, question in
              (HELD_OUT if args.suite == 'heldout' else CASES)] if args.suite != 'conversations'
             else [(f'{thread}_{index}', question, thread) for thread, questions in CONVERSATIONS
                   for index, question in enumerate(questions, 1)])
    selected = set(args.cases.split(',')) if args.cases else None
    for identity, question, thread in cases:
        if selected and identity not in selected:
            continue
        artifact = {'id': identity, 'question': question, 'calls': []}

        def capture(client, prompt, **options):
            call = {'prompt': prompt, 'image_labels': [image.label for image in options.get('images', [])]}
            artifact['calls'].append(call)
            raw = original_generate(client, prompt, **options)
            call['response'] = raw
            return raw

        trace = {}
        history = histories.setdefault(thread, []) if thread else []
        artifact['history'] = list(history)
        started = perf_counter()
        try:
            with patch.object(GenerationClient, 'generate', capture):
                reply = await handle_query(question, scope=scope, history=history, admin_trace=trace)
            artifact.update(reply=reply, trace=trace)
            if thread:
                history.extend([{'role': 'user', 'content': question},
                                {'role': 'assistant', 'content': reply['answer']}])
        except Exception as error:
            artifact['error'] = type(error).__name__
            logging.exception('Evaluation case failed: %s', identity)
        artifact['latency_seconds'] = round(perf_counter() - started, 3)
        (output / f'{identity}.json').write_text(json.dumps(artifact, ensure_ascii=False, indent=2))
        reply = artifact.get('reply', {})
        summary = {key: artifact[key] for key in ('id', 'question', 'latency_seconds')}
        summary.update(response_type=reply.get('response_type'), answer=reply.get('answer'),
                       sources=len(reply.get('sources', [])), attachments=len(reply.get('attachments', [])),
                       videos=len(reply.get('videos', [])), error=artifact.get('error'))
        results.append(summary)
        (output / 'summary.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
        print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope', default='output/recovery/baseline-20261104/scope.json')
    parser.add_argument('--output', required=True)
    parser.add_argument('--cases', help='Comma-separated case IDs; omitted runs the 30-case set.')
    parser.add_argument('--suite', choices=['standard', 'heldout', 'conversations'], default='standard')
    args = parser.parse_args()
    asyncio.run(evaluate(args))
