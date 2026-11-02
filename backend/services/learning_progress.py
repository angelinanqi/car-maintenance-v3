"""Account-owned learning state shared by the mobile readers."""
from backend import db
from fastapi import HTTPException
from postgrest.exceptions import APIError


def save(user_id, guide_id, values, previous):
    """Compare the persisted revision instead of overwriting a concurrent save."""
    table = db.client().table('learning_progress')
    if previous:
        rows = (table.update(values).eq('user_id', user_id).eq('id', guide_id)
                .eq('updated_at', previous['updated_at']).execute().data)
        if rows:
            return rows[0]
    else:
        try:
            return table.insert({**values, 'user_id': user_id, 'id': guide_id}).execute().data[0]
        except APIError as error:
            if error.code != '23505':
                raise
    raise HTTPException(409, 'Learning progress changed. Refresh it and try again.')


def snapshot(user_id):
    progress = db.all_rows('learning_progress', user_id=user_id)
    recaps = db.all_rows('learning_recaps', user_id=user_id)
    return {
        'learningProgress': [{key: row.get(key) for key in
                              ('id', 'completed', 'current_step_id', 'guide_revision', 'completed_at')}
                             for row in progress],
        'completedLessons': [row['id'] for row in progress if row['completed']],
        'completedRecaps': [row['id'] for row in recaps],
    }
