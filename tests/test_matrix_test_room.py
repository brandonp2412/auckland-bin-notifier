from auckland_bin_notifier.matrix_test_room import private_members


def test_only_own_member_is_permitted():
    owner = {"type": "m.room.member", "state_key": "@brandon:example.org", "content": {"membership": "join"}}
    other = {"type": "m.room.member", "state_key": "@someone:example.org", "content": {"membership": "invite"}}
    assert private_members([owner], "@brandon:example.org")
    assert not private_members([owner, other], "@brandon:example.org")
    assert not private_members([], "@brandon:example.org")
