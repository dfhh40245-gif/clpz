"""F21 probe: JS URL() normalizes backslashes to slashes, so '/\\evil.com'
passes a startsWith('/') + !startsWith('//') guard yet resolves OFF-origin.
Python's urljoin approximates the WHATWG resolution for the backslash case;
the definitive check is the Node repro recorded in the audit."""
from urllib.parse import urljoin

origin = "https://clpz.example"
cases = ["/normal", "/\\untrusted.example", "//untrusted.example"]
for payload in cases:
    js_guard_passes = payload.startswith("/") and not payload.startswith("//")
    resolved = urljoin(origin, payload.replace("\\", "/"))
    off_origin = not resolved.startswith(origin)
    print(f"payload={payload!r:28} guard_pass={js_guard_passes!s:5} resolved={resolved} off_origin={off_origin}")
