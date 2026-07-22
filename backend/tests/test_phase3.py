"""Phase 3 tests: lead type, contract party, referral tracking.

Terv: INTEGRATION_PLAN.md "Fazis 3 - Lead-tipus, szerzodo fel, beajanlo".
"""
import pytest


class TestLeadType:
    """3: Deal.lead_type (single/double) + contract_company_id/
    contract_contact_id, no stage guard tied to these fields."""

    def test_default_lead_type_is_single(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p3 default lead type"})
        d = r.json()
        try:
            assert d["lead_type"] == "single"
            assert d["contract_company_id"] is None
            assert d["contract_contact_id"] is None
        finally:
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")

    def test_double_lead_type_with_contract_party(self, admin_client, base_url):
        company = admin_client.post(f"{base_url}/api/companies", json={"name": "TEST_p3 contract co"}).json()
        contact = admin_client.post(f"{base_url}/api/contacts", json={"first_name": "TEST_p3 contract contact"}).json()
        try:
            r = admin_client.post(f"{base_url}/api/deals", json={
                "title": "TEST_p3 double lead", "lead_type": "double",
                "contract_company_id": company["id"], "contract_contact_id": contact["id"],
            })
            assert r.status_code == 200, r.text
            d = r.json()
            try:
                assert d["lead_type"] == "double"
                assert d["contract_company_id"] == company["id"]
                assert d["contract_contact_id"] == contact["id"]
            finally:
                admin_client.delete(f"{base_url}/api/deals/{d['id']}")
        finally:
            admin_client.delete(f"{base_url}/api/companies/{company['id']}")
            admin_client.delete(f"{base_url}/api/contacts/{contact['id']}")

    def test_invalid_lead_type_rejected(self, admin_client, base_url):
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p3 bad lead type", "lead_type": "triple"})
        assert r.status_code == 422

    def test_double_lead_type_does_not_block_won_stage(self, admin_client, base_url):
        """3: 'Stadium-guard: most nem' -- lead_type/contract_* completeness
        must not gate stage progression (that's explicitly out of scope)."""
        r = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p3 double no guard", "lead_type": "double"})
        d = r.json()
        try:
            sr = admin_client.patch(f"{base_url}/api/deals/{d['id']}/stage", json={"stage": "won"})
            assert sr.status_code == 200, sr.text
        finally:
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")

    def test_put_updates_lead_type_and_contract_fields(self, admin_client, base_url):
        company = admin_client.post(f"{base_url}/api/companies", json={"name": "TEST_p3 put contract co"}).json()
        d = admin_client.post(f"{base_url}/api/deals", json={"title": "TEST_p3 put lead type"}).json()
        try:
            payload = {**{k: d[k] for k in ("title", "value", "currency", "stage", "probability",
                                            "expected_close", "notes", "company_id", "contact_id", "source")},
                      "lead_type": "double", "contract_company_id": company["id"]}
            r = admin_client.put(f"{base_url}/api/deals/{d['id']}", json=payload)
            assert r.status_code == 200, r.text
            assert r.json()["lead_type"] == "double"
            assert r.json()["contract_company_id"] == company["id"]
        finally:
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")
            admin_client.delete(f"{base_url}/api/companies/{company['id']}")

    def test_contract_fields_settable_while_lead_type_single(self, admin_client, base_url):
        """3: contract_* is deliberately unvalidated against lead_type
        (schemas.py comment) -- this documents that non-coupling as a
        contract, not just a comment."""
        company = admin_client.post(f"{base_url}/api/companies", json={"name": "TEST_p3 single+contract co"}).json()
        try:
            r = admin_client.post(f"{base_url}/api/deals", json={
                "title": "TEST_p3 single with contract", "lead_type": "single",
                "contract_company_id": company["id"],
            })
            assert r.status_code == 200, r.text
            d = r.json()
            try:
                assert d["lead_type"] == "single"
                assert d["contract_company_id"] == company["id"]
            finally:
                admin_client.delete(f"{base_url}/api/deals/{d['id']}")
        finally:
            admin_client.delete(f"{base_url}/api/companies/{company['id']}")

    def test_delete_referenced_company_nulls_contract_company_id(self, admin_client, base_url):
        company = admin_client.post(f"{base_url}/api/companies", json={"name": "TEST_p3 del contract co"}).json()
        d = admin_client.post(f"{base_url}/api/deals", json={
            "title": "TEST_p3 del contract co deal", "lead_type": "double",
            "contract_company_id": company["id"],
        }).json()
        try:
            r = admin_client.delete(f"{base_url}/api/companies/{company['id']}")
            assert r.status_code == 200, r.text
            refreshed = admin_client.get(f"{base_url}/api/deals").json()
            match = next(x for x in refreshed if x["id"] == d["id"])
            assert match["contract_company_id"] is None
        finally:
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")

    def test_delete_referenced_contact_nulls_contract_contact_id(self, admin_client, base_url):
        contact = admin_client.post(f"{base_url}/api/contacts", json={"first_name": "TEST_p3 del contract contact"}).json()
        d = admin_client.post(f"{base_url}/api/deals", json={
            "title": "TEST_p3 del contract contact deal", "lead_type": "double",
            "contract_contact_id": contact["id"],
        }).json()
        try:
            r = admin_client.delete(f"{base_url}/api/contacts/{contact['id']}")
            assert r.status_code == 200, r.text
            refreshed = admin_client.get(f"{base_url}/api/deals").json()
            match = next(x for x in refreshed if x["id"] == d["id"])
            assert match["contract_contact_id"] is None
        finally:
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")

    def test_delete_referenced_contact_nulls_referred_by_contact_id(self, admin_client, base_url):
        contact = admin_client.post(f"{base_url}/api/contacts", json={"first_name": "TEST_p3 del referrer contact"}).json()
        d = admin_client.post(f"{base_url}/api/deals", json={
            "title": "TEST_p3 del referrer deal", "referred_by_contact_id": contact["id"],
        }).json()
        try:
            r = admin_client.delete(f"{base_url}/api/contacts/{contact['id']}")
            assert r.status_code == 200, r.text
            refreshed = admin_client.get(f"{base_url}/api/deals").json()
            match = next(x for x in refreshed if x["id"] == d["id"])
            assert match["referred_by_contact_id"] is None
        finally:
            admin_client.delete(f"{base_url}/api/deals/{d['id']}")


class TestReferral:
    """3: Deal.referred_by_contact_id + request-time referral rollup on
    GET /contacts/{id}/detail."""

    def test_referred_by_round_trips(self, admin_client, base_url):
        referrer = admin_client.post(f"{base_url}/api/contacts", json={"first_name": "TEST_p3 referrer"}).json()
        try:
            r = admin_client.post(f"{base_url}/api/deals", json={
                "title": "TEST_p3 referred deal", "referred_by_contact_id": referrer["id"],
            })
            d = r.json()
            try:
                assert d["referred_by_contact_id"] == referrer["id"]
            finally:
                admin_client.delete(f"{base_url}/api/deals/{d['id']}")
        finally:
            admin_client.delete(f"{base_url}/api/contacts/{referrer['id']}")

    def test_referral_rollup_counts_and_won(self, admin_client, base_url):
        referrer = admin_client.post(f"{base_url}/api/contacts", json={"first_name": "TEST_p3 rollup referrer"}).json()
        deal_ids = []
        try:
            d1 = admin_client.post(f"{base_url}/api/deals", json={
                "title": "TEST_p3 rollup deal 1", "referred_by_contact_id": referrer["id"],
            }).json()
            deal_ids.append(d1["id"])
            d2 = admin_client.post(f"{base_url}/api/deals", json={
                "title": "TEST_p3 rollup deal 2", "referred_by_contact_id": referrer["id"],
            }).json()
            deal_ids.append(d2["id"])
            admin_client.patch(f"{base_url}/api/deals/{d2['id']}/stage", json={"stage": "won"})

            detail = admin_client.get(f"{base_url}/api/contacts/{referrer['id']}/detail").json()
            assert detail["referrals"]["count"] == 2
            assert detail["referrals"]["won_count"] == 1
        finally:
            for did in deal_ids:
                admin_client.delete(f"{base_url}/api/deals/{did}")
            admin_client.delete(f"{base_url}/api/contacts/{referrer['id']}")

    def test_referral_rollup_counts_lost_deal_but_not_as_won(self, admin_client, base_url):
        referrer = admin_client.post(f"{base_url}/api/contacts", json={"first_name": "TEST_p3 lost rollup referrer"}).json()
        deal_ids = []
        try:
            d1 = admin_client.post(f"{base_url}/api/deals", json={
                "title": "TEST_p3 lost rollup deal 1", "referred_by_contact_id": referrer["id"],
            }).json()
            deal_ids.append(d1["id"])
            d2 = admin_client.post(f"{base_url}/api/deals", json={
                "title": "TEST_p3 lost rollup deal 2 won", "referred_by_contact_id": referrer["id"],
            }).json()
            deal_ids.append(d2["id"])
            d3 = admin_client.post(f"{base_url}/api/deals", json={
                "title": "TEST_p3 lost rollup deal 3 lost", "referred_by_contact_id": referrer["id"],
            }).json()
            deal_ids.append(d3["id"])
            admin_client.patch(f"{base_url}/api/deals/{d2['id']}/stage", json={"stage": "won"})
            admin_client.patch(f"{base_url}/api/deals/{d3['id']}/stage", json={"stage": "lost"})

            detail = admin_client.get(f"{base_url}/api/contacts/{referrer['id']}/detail").json()
            assert detail["referrals"]["count"] == 3
            assert detail["referrals"]["won_count"] == 1
        finally:
            for did in deal_ids:
                admin_client.delete(f"{base_url}/api/deals/{did}")
            admin_client.delete(f"{base_url}/api/contacts/{referrer['id']}")

    def test_contact_as_both_direct_party_and_referrer_lists_dont_cross_contaminate(self, admin_client, base_url):
        contact = admin_client.post(f"{base_url}/api/contacts", json={"first_name": "TEST_p3 dual role contact"}).json()
        deal_ids = []
        try:
            direct = admin_client.post(f"{base_url}/api/deals", json={
                "title": "TEST_p3 dual role direct deal", "contact_id": contact["id"],
            }).json()
            deal_ids.append(direct["id"])
            referred = admin_client.post(f"{base_url}/api/deals", json={
                "title": "TEST_p3 dual role referred deal", "referred_by_contact_id": contact["id"],
            }).json()
            deal_ids.append(referred["id"])

            detail = admin_client.get(f"{base_url}/api/contacts/{contact['id']}/detail").json()
            deal_titles = {d["title"] for d in detail["deals"]}
            assert deal_titles == {"TEST_p3 dual role direct deal"}
            assert detail["referrals"]["count"] == 1
        finally:
            for did in deal_ids:
                admin_client.delete(f"{base_url}/api/deals/{did}")
            admin_client.delete(f"{base_url}/api/contacts/{contact['id']}")

    def test_referral_rollup_zero_for_contact_with_no_referrals(self, admin_client, base_url):
        c = admin_client.post(f"{base_url}/api/contacts", json={"first_name": "TEST_p3 no referrals"}).json()
        try:
            detail = admin_client.get(f"{base_url}/api/contacts/{c['id']}/detail").json()
            assert detail["referrals"]["count"] == 0
            assert detail["referrals"]["won_count"] == 0
        finally:
            admin_client.delete(f"{base_url}/api/contacts/{c['id']}")

    def test_referral_rollup_excludes_private_deal_non_member_cannot_see(self, admin_client, user_client, base_url):
        referrer = admin_client.post(f"{base_url}/api/contacts", json={"first_name": "TEST_p3 private referrer"}).json()
        try:
            d = admin_client.post(f"{base_url}/api/deals", json={
                "title": "TEST_p3 private referred deal", "referred_by_contact_id": referrer["id"],
            }).json()
            try:
                admin_client.patch(f"{base_url}/api/deals/{d['id']}/visibility", json={"visibility": "private"})
                as_admin = admin_client.get(f"{base_url}/api/contacts/{referrer['id']}/detail").json()
                assert as_admin["referrals"]["count"] == 1
                as_user = user_client.get(f"{base_url}/api/contacts/{referrer['id']}/detail").json()
                assert as_user["referrals"]["count"] == 0
            finally:
                admin_client.delete(f"{base_url}/api/deals/{d['id']}")
        finally:
            admin_client.delete(f"{base_url}/api/contacts/{referrer['id']}")

    def test_regular_referrer_tag_round_trips_via_existing_tags_field(self, admin_client, base_url):
        c = admin_client.post(f"{base_url}/api/contacts", json={"first_name": "TEST_p3 tag contact"}).json()
        try:
            r = admin_client.put(f"{base_url}/api/contacts/{c['id']}", json={
                "first_name": "TEST_p3 tag contact", "tags": ["referrer"],
            })
            assert r.status_code == 200, r.text
            assert r.json()["tags"] == ["referrer"]
        finally:
            admin_client.delete(f"{base_url}/api/contacts/{c['id']}")
