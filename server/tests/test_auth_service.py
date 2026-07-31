import pytest

from services.auth import authenticate, get_user, normalize_username, register


@pytest.fixture()
def ctx(app):
    with app.app_context():
        yield


def test_normalize_username_trims_and_lowercases():
    assert normalize_username('  Ada  ') == 'ada'


def test_register_creates_user(ctx):
    user = register('Ada', 'password1', 'Ada', 'Lovelace')
    assert user == {
        'userId': user['userId'],
        'username': 'ada',
        'firstName': 'Ada',
        'lastName': 'Lovelace',
    }


def test_register_rejects_duplicate_username_case_insensitively(ctx):
    register('Ada', 'password1', 'Ada', 'Lovelace')
    assert register('ADA', 'password2', 'Someone', 'Else') is None


def test_authenticate_succeeds_with_correct_password(ctx):
    created = register('Ada', 'password1', 'Ada', 'Lovelace')
    user = authenticate('ada', 'password1')
    assert user == created


def test_authenticate_fails_with_wrong_password(ctx):
    register('Ada', 'password1', 'Ada', 'Lovelace')
    assert authenticate('ada', 'wrong-password') is None


def test_authenticate_fails_for_unknown_user(ctx):
    assert authenticate('nobody', 'password1') is None


def test_get_user_returns_none_for_unknown_id(ctx):
    assert get_user(999) is None


def test_get_user_returns_serialized_user(ctx):
    created = register('Ada', 'password1', 'Ada', 'Lovelace')
    assert get_user(created['userId']) == created
