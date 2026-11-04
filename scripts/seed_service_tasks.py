"""Populate the petrol ICE service-task catalogue without changing existing records.

Run: python -m scripts.seed_service_tasks [--apply]
Intervals and vehicle applicability belong in reviewed vehicle schedules.
"""
import argparse
from uuid import NAMESPACE_URL, uuid5

from backend import db

# Each operation has its own identity so inspections and replacements can have
# different schedule rules and service histories.
GROUPS = {
    'Engine and lubrication': [
        ('inspect', 'Check engine oil level'),
        ('replace', 'Replace engine oil'),
        ('replace', 'Replace engine oil filter'),
        ('inspect', 'Inspect engine for oil leaks'),
        ('inspect', 'Inspect engine mounts'),
        ('inspect', 'Inspect drive belts and tensioners'),
        ('replace', 'Replace drive belt'),
        ('inspect', 'Inspect timing belt'),
        ('replace', 'Replace timing belt and tensioners'),
        ('inspect', 'Inspect valve clearance'),
        ('service', 'Adjust valve clearance'),
    ],
    'Air, fuel and ignition': [
        ('inspect', 'Inspect engine air filter'),
        ('replace', 'Replace engine air filter'),
        ('replace', 'Replace fuel filter'),
        ('inspect', 'Inspect fuel lines and connections'),
        ('inspect', 'Inspect spark plugs'),
        ('replace', 'Replace spark plugs'),
        ('inspect', 'Inspect ignition coils and leads'),
        ('inspect', 'Inspect intake hoses and vacuum lines'),
        ('inspect', 'Inspect crankcase ventilation system'),
        ('replace', 'Replace PCV valve'),
    ],
    'Cooling system': [
        ('inspect', 'Check engine coolant level and condition'),
        ('replace', 'Replace engine coolant'),
        ('inspect', 'Inspect radiator, hoses and connections'),
        ('inspect', 'Inspect cooling fan operation'),
        ('inspect', 'Inspect radiator cap and expansion tank'),
        ('inspect', 'Inspect water pump for leaks'),
    ],
    'Transmission and drivetrain': [
        ('inspect', 'Inspect transmission fluid level and condition'),
        ('inspect', 'Inspect transmission for leaks'),
        ('replace', 'Replace automatic transmission fluid'),
        ('replace', 'Replace CVT fluid'),
        ('replace', 'Replace dual-clutch transmission fluid'),
        ('replace', 'Replace manual transmission oil'),
        ('replace', 'Replace transmission filter'),
        ('replace', 'Replace differential oil'),
        ('replace', 'Replace transfer case oil'),
        ('inspect', 'Inspect driveshafts and CV boots'),
        ('inspect', 'Inspect propeller shaft and universal joints'),
        ('inspect', 'Inspect clutch operation'),
        ('replace', 'Replace clutch hydraulic fluid'),
    ],
    'Brakes': [
        ('inspect', 'Check brake fluid level and condition'),
        ('replace', 'Replace brake fluid'),
        ('inspect', 'Inspect brake pads and discs'),
        ('replace', 'Replace brake pads'),
        ('replace', 'Replace brake discs'),
        ('inspect', 'Inspect brake shoes and drums'),
        ('replace', 'Replace brake shoes'),
        ('replace', 'Replace brake drums'),
        ('inspect', 'Inspect brake hoses, pipes and connections'),
        ('inspect', 'Inspect parking brake operation'),
        ('service', 'Adjust parking brake'),
        ('service', 'Service brake caliper slides'),
    ],
    'Tyres and wheels': [
        ('inspect', 'Check tyre pressure including spare tyre'),
        ('inspect', 'Inspect tyre tread, wear and damage'),
        ('service', 'Rotate tyres'),
        ('service', 'Balance wheels'),
        ('service', 'Check and adjust wheel alignment'),
        ('replace', 'Replace tyres'),
        ('inspect', 'Inspect wheels and wheel fasteners'),
        ('inspect', 'Inspect wheel bearings'),
        ('inspect', 'Inspect tyre repair kit and inflator'),
    ],
    'Steering and suspension': [
        ('inspect', 'Inspect steering linkage and rack boots'),
        ('inspect', 'Inspect ball joints and suspension bushes'),
        ('inspect', 'Inspect shock absorbers, struts and springs'),
        ('inspect', 'Check power steering fluid level and condition'),
        ('replace', 'Replace power steering fluid'),
        ('inspect', 'Inspect power steering hoses for leaks'),
    ],
    'Battery and electrical': [
        ('inspect', 'Test 12-volt battery condition'),
        ('service', 'Clean and secure battery terminals'),
        ('replace', 'Replace 12-volt battery'),
        ('inspect', 'Inspect charging and starting systems'),
        ('inspect', 'Check exterior lights and indicators'),
        ('replace', 'Replace exterior light bulbs'),
        ('inspect', 'Check horn operation'),
        ('inspect', 'Check dashboard warning lights'),
        ('service', 'Perform diagnostic fault-code scan'),
    ],
    'Air conditioning and cabin': [
        ('inspect', 'Inspect cabin air filter'),
        ('replace', 'Replace cabin air filter'),
        ('inspect', 'Check air conditioning and heater operation'),
        ('inspect', 'Inspect air conditioning refrigerant lines'),
        ('service', 'Clean air conditioning evaporator drain'),
    ],
    'Visibility, body and safety': [
        ('inspect', 'Check windscreen washer fluid level'),
        ('service', 'Top up windscreen washer fluid'),
        ('inspect', 'Inspect wiper blades and washer operation'),
        ('replace', 'Replace front wiper blades'),
        ('replace', 'Replace rear wiper blade'),
        ('inspect', 'Inspect windscreen and mirrors'),
        ('inspect', 'Inspect seat belts and buckles'),
        ('service', 'Lubricate door hinges, locks and latches'),
        ('inspect', 'Inspect underbody for damage and corrosion'),
        ('inspect', 'Inspect exhaust system and mountings'),
        ('inspect', 'Inspect fuel tank cap and seal'),
    ],
}


def catalogue_rows():
    rows = []
    for category, tasks in GROUPS.items():
        for action, title in tasks:
            rows.append({
                'id': str(uuid5(NAMESPACE_URL, 'roadie:service-task:' + action + ':' + title.lower())),
                'title': title, 'category': category, 'action': action, 'active': True,
                'description': (
                    f'{title}. Use only where applicable to the vehicle and its equipment. '
                    'Follow the vehicle manufacturer’s procedure and reviewed service schedule; '
                    'replacement or corrective work depends on the specified interval or inspection findings.'
                ),
            })
    return rows


def seed(*, apply=False):
    existing = db.all_rows('maintenance_items')
    identities = {(r['title'].strip().lower(), r['action']) for r in existing}
    missing = [r for r in catalogue_rows() if (r['title'].strip().lower(), r['action']) not in identities]
    print(f'{len(existing)} existing tasks; {len(missing)} missing standard tasks.')
    if not apply:
        print('Preview only. Use --apply to insert missing tasks.')
        return
    if missing:
        # Ignore concurrent inserts with the same stable seed ID. Never update
        # user edits or reactivate items an administrator has deactivated.
        db.client().table('maintenance_items').upsert(
            missing, on_conflict='id', ignore_duplicates=True,
        ).execute()
    saved = db.all_rows('maintenance_items')
    saved_ids = {r['id'] for r in saved}
    saved_keys = {(r['title'].strip().lower(), r['action']) for r in saved}
    assert all(r['id'] in saved_ids or (r['title'].strip().lower(), r['action']) in saved_keys
               for r in catalogue_rows()), 'Some standard tasks were not saved.'
    print(f'Verified {len(saved)} saved service tasks. Existing records preserved.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    seed(apply=parser.parse_args().apply)
