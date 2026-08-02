from atlas.assets.affiliate_department.models import AffiliateOpportunity
from atlas.assets.affiliate_department.store import AffiliateStore


def test_round_trips_an_opportunity(tmp_path):
    store = AffiliateStore(tmp_path / "affiliate_department.json")
    opportunity = AffiliateOpportunity(product_name="KetoDNA", description="a keto diet offer")
    store.save_opportunity(opportunity)

    assert store.get_opportunity(opportunity.id).product_name == "KetoDNA"


def test_write_is_atomic_and_leaves_no_stray_temp_file(tmp_path):
    path = tmp_path / "affiliate_department.json"
    store = AffiliateStore(path)
    store.save_opportunity(AffiliateOpportunity(product_name="KetoDNA", description="a keto diet offer"))

    assert path.exists()
    assert not path.with_name(path.name + ".tmp").exists()
