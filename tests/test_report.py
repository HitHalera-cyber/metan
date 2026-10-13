import zipfile

from metan import Params, Solver, report, studies


def test_word_report(tmp_path):
    p = Params(NVARM=2, NMAX=40, NPRINT=10)
    r = Solver(p).run()
    s = studies.run_series(p, "DKR", [7.5, 8.0])
    path = report.build(str(tmp_path / "r.docx"), r, series=s)
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
        images = [n for n in z.namelist() if n.startswith("word/media/")]
    assert "Исходные данные" in xml and "Рисунок 1" in xml
    assert len(images) >= 5
