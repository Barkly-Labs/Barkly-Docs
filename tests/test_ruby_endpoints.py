from pathlib import Path
from bs4 import BeautifulSoup
from model.project import Project
from readers.ruby import RubyReader
from analysis.graph import build_relation_graph
from rendering.entities_page import render_entities_page


def scan(tmp_path: Path, source: str):
    path=tmp_path/'app.rb'; path.write_text(source, encoding='utf-8')
    project=Project(name='ruby-app', root=str(tmp_path))
    result=RubyReader().read(path, project)
    assert result.success, result.errors
    return path, project


def test_sinatra_routes_enter_shared_model_graph_and_entities(tmp_path):
    path, project=scan(tmp_path, '''\
require 'sinatra/base'

class App < Sinatra::Base
  # Returns the home page.
  get '/home' do
    'ok'
  end

  post(
    "/users/:id",
    provides: :json
  ) do
    'created'
  end
end
''')
    assert [(e.method,e.path) for e in project.endpoints] == [('GET','/home'),('POST','/users/:id')]
    first=project.endpoints[0]
    assert first.source_file == str(path)
    assert first.metadata['line'] == 5
    assert first.metadata['enclosing'] == 'App'
    assert first.documentation == 'Returns the home page.'
    assert first.metadata['evidence'] == 'DETECTED'
    assert 'provides: :json' in project.endpoints[1].metadata['route_options']

    graph=build_relation_graph(project)
    endpoint_nodes=[n for n in graph.nodes if n.kind == 'endpoint']
    assert {n.label for n in endpoint_nodes} == {'GET /home','POST /users/:id'}
    assert len({n.id for n in endpoint_nodes}) == 2

    html=render_entities_page(project)
    soup=BeautifulSoup(html,'html.parser')
    text=soup.get_text(' ', strip=True)
    assert 'GET /home' in text and 'POST /users/:id' in text
    assert str(path) in html
    assert 'Returns the home page.' in text


def test_http_words_in_comments_strings_and_non_sinatra_files_are_not_routes(tmp_path):
    _, project=scan(tmp_path, '''\
# get '/comment' do
TEXT = "post '/string' do"
def get(value)
  value
end
get('/ordinary-method')
''')
    assert project.endpoints == []


def test_sinatra_comment_and_string_false_positives_are_ignored(tmp_path):
    _, project=scan(tmp_path, '''\
require 'sinatra'
# get '/comment' do
EXAMPLE = "post '/string' do"
get '/real' do
  'yes'
end
''')
    assert [(e.method,e.path) for e in project.endpoints] == [('GET','/real')]


def test_all_supported_sinatra_http_verbs_and_regex_patterns(tmp_path):
    lines=["require 'sinatra'"]
    for verb in ('get','post','put','patch','delete','options','head','connect','trace','link','unlink'):
        lines += [f"{verb} '/{verb}' do", "  'ok'", 'end']
    lines += [r"get %r{/items/\d+} do", "  'ok'", 'end']
    _, project=scan(tmp_path, '\n'.join(lines)+'\n')
    assert [e.method for e in project.endpoints[:11]] == [v.upper() for v in ('get','post','put','patch','delete','options','head','connect','trace','link','unlink')]
    assert project.endpoints[-1].path == r'%r{/items/\d+}'


def test_dynamic_route_is_left_unresolved_not_invented(tmp_path):
    _, project=scan(tmp_path, "require 'sinatra'\npath = '/x'\nget path do\n 'x'\nend\n")
    assert project.endpoints == []


def test_require_sinatra_base_does_not_enable_top_level_route_dsl(tmp_path):
    _, project=scan(tmp_path, "require 'sinatra/base'\nget '/not-a-class-route' do\n 'x'\nend\n")
    assert project.endpoints == []
