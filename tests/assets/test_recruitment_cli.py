from atlas.cli import main


def test_full_intake_and_approval_flow(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    main(
        [
            "recruitment",
            "demand",
            "add",
            "--industry",
            "construction",
            "--employer-name",
            "BuildCo",
            "--role",
            "Laborer",
            "--headcount",
            "1",
            "--rate",
            "40.0",
        ]
    )
    capsys.readouterr()

    main(["recruitment", "supplier", "add", "--name", "City Labor Pool", "--industry", "construction"])
    supplier_id = capsys.readouterr().out.strip().split("\t")[0]

    main(
        [
            "recruitment",
            "candidate",
            "add",
            "--industry",
            "construction",
            "--description",
            "Laborer A",
            "--pay-rate",
            "25.0",
            "--supplier-id",
            supplier_id,
        ]
    )
    capsys.readouterr()

    for _ in range(4):  # discovered -> qualified -> matched -> proposal_ready
        main(["run", "recruitment_workforce"])
    capsys.readouterr()

    main(["recruitment", "opportunities"])
    opportunities_out = capsys.readouterr().out
    assert "proposal_ready" in opportunities_out
    opp_id = opportunities_out.strip().split("\t")[0]

    main(["recruitment", "approve-outreach", opp_id])
    assert "active" in capsys.readouterr().out

    main(["recruitment", "approve-commitment", opp_id])
    assert "won" in capsys.readouterr().out


def test_approve_outreach_wrong_stage_exits_nonzero(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["run", "recruitment_workforce"])  # seeds + creates a "discovered" opportunity
    capsys.readouterr()
    main(["recruitment", "opportunities"])
    opp_id = capsys.readouterr().out.strip().split("\t")[0]

    exit_code = main(["recruitment", "approve-outreach", opp_id])

    assert exit_code == 1
    assert "not awaiting outreach approval" in capsys.readouterr().err


def test_approve_commitment_wrong_stage_exits_nonzero(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["run", "recruitment_workforce"])
    capsys.readouterr()
    main(["recruitment", "opportunities"])
    opp_id = capsys.readouterr().out.strip().split("\t")[0]

    exit_code = main(["recruitment", "approve-commitment", opp_id])

    assert exit_code == 1
    assert "not awaiting commitment approval" in capsys.readouterr().err


def test_mark_lost(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["run", "recruitment_workforce"])
    capsys.readouterr()
    main(["recruitment", "opportunities"])
    opp_id = capsys.readouterr().out.strip().split("\t")[0]

    main(["recruitment", "lost", opp_id, "--reason", "employer cancelled"])

    assert "lost" in capsys.readouterr().out


def test_unknown_opportunity_id_exits_nonzero(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    exit_code = main(["recruitment", "approve-outreach", "does-not-exist"])

    assert exit_code == 1
    assert "no such opportunity" in capsys.readouterr().err
