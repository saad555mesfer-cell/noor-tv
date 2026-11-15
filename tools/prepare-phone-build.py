#!/usr/bin/env python3
"""Prepare the reference launcher for installing the Riyadh theme from a phone."""
import json
import pathlib
import shutil
import sys
import xml.etree.ElementTree as ET

root = pathlib.Path(sys.argv[1])
repo = pathlib.Path(__file__).resolve().parents[1]
src = root / "launcher/app/src/main"
java = src / "java/com/gathin/tvhome"

def replace_once(path, before, after):
    text = path.read_text()
    if text.count(before) != 1:
        raise SystemExit(f"Unexpected upstream source in {path}: expected one patch location")
    path.write_text(text.replace(before, after, 1))

# The upstream launcher accepts time groups only; retain the base groups and add weather groups.
names = ["morning", "evening", "night"]
groups = names + [f"{time}-{weather}" for time in names for weather in ("clear", "cloudy", "rain", "dust")]
replace_once(java / "WallpaperMood.java",
             "static final String[] ALL = {MORNING, EVENING, NIGHT};",
             "static final String[] ALL = {" + ", ".join(json.dumps(x) for x in groups) + "};")
replace_once(java / "WallpaperPlayer.java",
    "return WallpaperMood.select(files, moods, WallpaperMood.timeOfDay(now.getHour() * 60 + now.getMinute(), sun[0], sun[1]));",
    """String time = WallpaperMood.timeOfDay(now.getHour() * 60 + now.getMinute(), sun[0], sun[1]);
        String weatherGroup = time + "-" + Noor.weatherKind();
        return WallpaperMood.select(files, moods, moods.containsKey(weatherGroup) ? weatherGroup : time);""")

# Bundle the theme inside the APK. Install it on first launch, without overwriting an existing theme.
theme = src / "assets/noor-theme"
theme.mkdir(parents=True, exist_ok=True)
shutil.copytree(repo / "themes/riyadh", theme, dirs_exist_ok=True)
config = json.loads((theme / "config.json").read_text())
config["locale"] = "ar"
(theme / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2))
replace_once(java / "Config.java",
    "return ctx.getExternalFilesDir(null);",
    """File directory = ctx.getExternalFilesDir(null);
        if (directory != null && !new File(directory, "config.json").exists()
                && !new File(directory, ".noor-theme-seeded").exists()) {
            try {
                seedNoorAssets(ctx.getAssets(), "noor-theme", directory);
                new File(directory, ".noor-theme-seeded").createNewFile();
            } catch (java.io.IOException e) {
                android.util.Log.w("NoorTheme", "Theme setup will retry next launch", e);
            }
        }
        return directory;""")
replace_once(java / "Config.java", "    static Config load(Context ctx) {",
    """    private static void seedNoorAssets(android.content.res.AssetManager assets, String path, File target)
            throws java.io.IOException {
        String[] children = assets.list(path);
        if (children != null && children.length > 0) {
            if (!target.isDirectory() && !target.mkdirs()) throw new java.io.IOException("Cannot create theme directory");
            for (String child : children) seedNoorAssets(assets, path + "/" + child, new File(target, child));
        } else {
            try (java.io.InputStream in = assets.open(path); FileOutputStream out = new FileOutputStream(target)) {
                byte[] buffer = new byte[8192];
                int count;
                while ((count = in.read(buffer)) != -1) out.write(buffer, 0, count);
            }
        }
    }

    static Config load(Context ctx) {""")

# Set the sun's location without requesting the TV's location permission.
cfg = src / "res/values/config.xml"
tree = ET.parse(cfg)
for name, value in (("latitude", "24.7136"), ("longitude", "46.6753")):
    node = tree.getroot().find(f"./string[@name='{name}']")
    if node is None:
        raise SystemExit(f"Missing launcher setting: {name}")
    node.text = value
tree.write(cfg, encoding="utf-8", xml_declaration=True)
print("Prepared Riyadh theme with time and weather backgrounds.")
