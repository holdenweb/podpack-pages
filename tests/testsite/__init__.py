"""A throwaway site package, existing so a test can override one app's template.

podpack resolves templates site first (ADR-0005), and "the site" is the package
`create_app(site_package=...)` names. Its `templates/pybooks/html.html` carries
a marker: a test proves the marker shows on pybooks pages and not on pages'.
"""
