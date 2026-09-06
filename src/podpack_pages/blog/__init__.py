"""The blog app: a Blogger blog, exported by sitescraper and served here.

sitescraper captures the blog into MongoDB and exports a tree of
content-only fragments with a manifest (`python -m blogscraper export`). That
tree is copied verbatim into this app's `export/` data directory, and this
app publishes it: each listed post has its placeholder root filled in with
whatever mount the site gave this app, and is wrapped in the site's chrome;
everything else in the tree is served as stored. Details of the contract are
in `publish.py` and `manifest.py`; the routes are in `views.py`.
"""

from typing import Any

from podpack import Health, Section, SiteApp, app_config
from podpack.paths import data_dir

from .manifest import EXPORT_TREE, ManifestError, load_manifest
from .views import FALLBACK_POST_TITLE, blueprint


class BlogApp(SiteApp):
    """Reports whether the manifest can be served, and which one it is.

    Both hooks run on podpack's own requests, so the app's name is passed
    rather than read from the blueprint in play.
    """

    def healthz(self) -> Health:
        # Not fatal: a blog without its export is a missing feature, not a
        # reason to stop the rest of the site serving.
        try:
            manifest = load_manifest(data_dir(self.name), FALLBACK_POST_TITLE)
        except ManifestError as exc:
            return Health(ok=False, detail=str(exc))
        return Health(ok=True, detail=f"{len(manifest.posts)} posts")

    def status(self) -> dict[str, Any]:
        # What an operator needs after copying an export in: which manifest
        # is live, and how many posts it lists.
        root = data_dir(self.name)
        report: dict[str, Any] = {
            "export": str(root / EXPORT_TREE),
            "image_root": app_config(self.name).get("image_root") or "(this app's mount)",
        }
        try:
            manifest = load_manifest(root, FALLBACK_POST_TITLE)
        except ManifestError as exc:
            report["manifest"] = {"error": str(exc)}
        else:
            report["manifest"] = {
                "generated_at": manifest.generated_at,
                "posts": len(manifest.posts),
            }
        return report


site_app = BlogApp(
    blueprint=blueprint,
    url_prefix="/blog",
    nav=(Section("Blog", "blog.index"),),
)
