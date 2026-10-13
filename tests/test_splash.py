from metan.app import splash


def test_stories_render(tmp_path):
    for key, (title, cls) in splash.STORIES.items():
        st = cls()
        for k in range(6):
            im = st.frame(st.length * k / 6)
            assert im.size == getattr(st, "size", (splash.W, splash.H))
    p = splash.render_gif("fortran", str(tmp_path / "f.gif"), scale=1, fps=4)
    assert (tmp_path / "f.gif").stat().st_size > 1000 and p


def test_text_width():
    assert splash.text_w("METAN") > splash.text_w("123")


def test_assets_present():
    from metan.app.assets import icon_paths, manual_path
    ico, png = icon_paths()
    assert ico and png and manual_path()


def test_city_both_themes():
    from metan.app.splash_stories import CityStory
    a = CityStory("dark").frame(5.0)
    b = CityStory("light").frame(5.0)
    # днём небо заметно светлее, чем ночью
    assert sum(b.getpixel((128, 5))) > sum(a.getpixel((128, 5))) + 200
