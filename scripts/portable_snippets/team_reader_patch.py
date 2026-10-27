"""Keep the existing editorial owner and validate the team's restricted gateway too."""
def patch(text):
    old='''    if not endpoint.startswith("https://") or not endpoint.endswith("/functions/v1/editorial-search"):
        raise BrainUnavailable("editorial brain function URL is invalid")
    if expected_project not in endpoint.split("/")[2].split("."):
        raise BrainUnavailable("function URL does not match configured Supabase project")'''
    new='''    from urllib.parse import urlsplit
    url = urlsplit(endpoint)
    if (url.scheme != "https" or url.hostname != expected_project + ".supabase.co"
            or url.path not in {"/functions/v1/editorial-search", "/functions/v1/vibe-editorial-read"}
            or url.port not in {None, 443} or url.username or url.password or url.query or url.fragment):
        raise BrainUnavailable("editorial brain function URL is invalid")'''
    if text.count(old)!=1:raise ValueError('Editorial reader endpoint contract changed')
    text=text.replace(old,new)
    old_open='with urllib.request.urlopen(request, timeout=timeout) as response:'
    replacement='# Never forward the dedicated team credential through an HTTP redirect.\n        class NoRedirect(urllib.request.HTTPRedirectHandler):\n            def redirect_request(self, req, fp, code, msg, headers, newurl):\n                return None\n        open_request = (urllib.request.build_opener(NoRedirect()).open\n                        if url.path.endswith("/vibe-editorial-read") else urllib.request.urlopen)\n        with open_request(request, timeout=timeout) as response:'
    if text.count(old_open)!=1:raise ValueError('Editorial reader request contract changed')
    return text.replace(old_open,replacement)
