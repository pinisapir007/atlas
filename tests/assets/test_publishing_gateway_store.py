from atlas.assets.publishing_gateway.models import PublishPackage
from atlas.assets.publishing_gateway.store import PublishingQueueStore


def _package() -> PublishPackage:
    return PublishPackage(platform="TikTok", title="KetoDNA launch", description="a keto diet offer", cta="Learn more")


def test_round_trips_a_package(tmp_path):
    store = PublishingQueueStore(tmp_path / "publishing_gateway.json")
    package = _package()
    store.save_package(package)

    assert store.get_package(package.id).title == "KetoDNA launch"


def test_delete_package_removes_it(tmp_path):
    store = PublishingQueueStore(tmp_path / "publishing_gateway.json")
    package = _package()
    store.save_package(package)
    store.delete_package(package.id)

    assert package.id not in [p.id for p in store.packages()]


def test_write_is_atomic_and_leaves_no_stray_temp_file(tmp_path):
    path = tmp_path / "publishing_gateway.json"
    store = PublishingQueueStore(path)
    store.save_package(_package())

    assert path.exists()
    assert not path.with_name(path.name + ".tmp").exists()
