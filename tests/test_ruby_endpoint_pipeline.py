from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from analysis.discovery import ProjectDiscovery
from readers.ruby import RubyReader
from rendering.html import render_project_website


@pytest.mark.slow
def test_ruby_endpoint_source_to_generated_html_pipeline(tmp_path):
    source=tmp_path/'app.rb'
    source.write_text("""require 'sinatra/base'\n\nclass API < Sinatra::Base\n  # Health check.\n  get '/health' do\n    'ok'\n  end\n\n  post('/items', provides: :json) { 'created' }\nend\n""", encoding='utf-8')
    result=ProjectDiscovery(readers=[RubyReader()]).analyze(tmp_path, name='endpoint-fixture')
    assert not result.errors
    assert [(e.method,e.path) for e in result.project.endpoints] == [('GET','/health'),('POST','/items')]
    graph=result.project.metadata['relation_graph']
    endpoint_nodes=[n for n in graph['nodes'] if n['kind']=='endpoint']
    assert {n['label'] for n in endpoint_nodes} == {'GET /health','POST /items'}

    out=tmp_path/'generated'
    render_project_website(result.project,out)
    index=BeautifulSoup((out/'index.html').read_text(encoding='utf-8'),'html.parser')
    entities=BeautifulSoup((out/'entities.html').read_text(encoding='utf-8'),'html.parser')
    relation=(out/'relation-map.html').read_text(encoding='utf-8')
    assert 'GET /health' in index.get_text(' ',strip=True)
    assert 'POST /items' in index.get_text(' ',strip=True)
    assert 'GET /health' in entities.get_text(' ',strip=True)
    assert 'Health check.' in entities.get_text(' ',strip=True)
    assert 'relation-map.js' in relation
