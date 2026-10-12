from auckland_bin_notifier.matrix_test_room import private_members


def test_only_own_member_is_permitted():
    owner = {"type": "m.room.member", "state_key": "@brandon:example.org", "content": {"membership": "join"}}
    other = {"type": "m.room.member", "state_key": "@someone:example.org", "content": {"membership": "invite"}}
    assert private_members([owner], "@brandon:example.org")
    assert not private_members([owner, other], "@brandon:example.org")
    assert not private_members([], "@brandon:example.org")


def test_bot_and_owner_may_share_lab_without_other_members():
    bot = {"type":"m.room.member","state_key":"@bins:matrix.presley.nz","content":{"membership":"join"}}
    owner = {"type":"m.room.member","state_key":"@brandon:matrix.presley.nz","content":{"membership":"join"}}
    other = {"type":"m.room.member","state_key":"@other:matrix.presley.nz","content":{"membership":"join"}}
    assert private_members([bot,owner],"@bins:matrix.presley.nz")
    assert not private_members([bot,owner,other],"@bins:matrix.presley.nz")
