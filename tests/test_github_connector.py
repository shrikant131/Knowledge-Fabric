from knowledge_fabric.connectors.github_connector import GitHubConnector

class FakeGitHub(GitHubConnector):
    def __init__(self):
        super().__init__("acme", "demo", source_id="gh")
    def _get(self, url):
        if url.endswith('/repos/acme/demo'):
            return {'default_branch':'main'}
        if '/commits/' in url:
            return {'sha':'abc123'}
        if '/git/trees/' in url:
            return {'truncated':False,'tree':[
                {'type':'blob','path':'src/a.py','sha':'1','size':20},
                {'type':'blob','path':'README.md','sha':'2','size':20},
                {'type':'blob','path':'node_modules/x.js','sha':'3','size':20},
            ]}
        if '/git/blobs/1' in url:
            import base64
            return {'encoding':'base64','content':base64.b64encode(b'def hello():\n    return "hi"\n').decode()}
        if '/git/blobs/2' in url:
            import base64
            return {'encoding':'base64','content':base64.b64encode(b'# Demo\n\nHello repository\n').decode()}
        raise AssertionError(url)

def test_github_fetch_filters_and_parses():
    c=FakeGitHub()
    items=list(c.fetch())
    assert [x.item_id for x in items] == ['src/a.py','README.md']
    assert items[0].extra['commit']=='abc123'
    chunks=c.chunk(c.parse(items[0]))
    assert any(x.symbol and 'hello' in x.symbol for x in chunks)
