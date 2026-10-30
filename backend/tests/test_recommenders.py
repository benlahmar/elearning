from types import SimpleNamespace

import numpy as np
import pytest
from sqlalchemy import select

from app.db import User
from app.recommenders.base import ModelUnavailable
from app.recommenders.mmr import select_mmr
from app.recommenders.registry import REGISTRY
from app.recommenders.service import recommend
from app.recommenders import semantic
from test_api import client


def resources():
    return [SimpleNamespace(id='a', title='Recommandation de vidéos', topic='Recommandation', tags=['recommandation'], description='Cours sur les recommandations'), SimpleNamespace(id='b', title='Recommandation de vidéos', topic='Recommandation', tags=['recommandation'], description='Cours sur les recommandations'), SimpleNamespace(id='c', title='Algèbre linéaire', topic='Mathématiques', tags=['matrices'], description='Calcul matriciel')]


@pytest.fixture
def fake_encoder(monkeypatch):
    def encode(texts):
        vectors = []
        for text in texts:
            vector = np.array([1.0 if 'recommand' in text.lower() else 0.0, 1.0 if ('matri' in text.lower() or 'algèbre' in text.lower()) else 0.0, .05])
            vectors.append(vector / np.linalg.norm(vector))
        return np.asarray(vectors, dtype=np.float32)
    semantic.semantic_index.cache_clear()
    monkeypatch.setattr(semantic.encoder, 'encode', encode)
    yield
    semantic.semantic_index.cache_clear()


def test_mmr_diversifies_and_lambda_one_preserves_relevance():
    ids = ('a','b','c')
    scores = np.array([1.0,.99,.8])
    matrix = np.array([[1,1,0],[1,1,0],[0,0,1]])
    similarity = lambda candidates, selected: matrix[np.ix_(candidates,selected)]
    assert select_mmr(ids,scores,similarity,2,1,3)[0] == [0,1]
    assert select_mmr(ids,scores,similarity,2,.3,3)[0] == [0,2]
    assert select_mmr(ids,scores,similarity,20,.3,3)[0] == [0,2,1]


def test_tfidf_rankings_cache_invalidation_and_no_signal():
    data=resources()
    result=recommend('tfidf',data,['recommandation'],{},2)
    assert [r.id for r, _ in result['ranked']] == ['a','b']
    assert result['ranked'][0][1] > 0
    result=recommend('tfidf',data,['vocabulaireinconnu'],{'c':5},2)
    assert result['fallback'] and result['effective_algorithm']=='popular'
    assert result['ranked'][0][0].id=='c'
    data[2].title='Recommandation recommandation'
    data[2].topic='recommandation'
    data[2].tags=['recommandation']
    data[2].description='recommandation'
    assert recommend('tfidf',data,['recommandation'],{},2)['ranked'][0][0].id=='c'


@pytest.mark.parametrize('id_', ['tfidf','tfidf_mmr','embeddings','embeddings_mmr','hybrid_content_mmr'])
def test_five_algorithms_empty_profile_and_empty_catalogue(id_):
    result=recommend(id_,resources(),[],{'c':2},6)
    assert result['effective_algorithm']=='popular'
    assert result['fallback']
    assert result['ranked'][0][0].id=='c'
    assert recommend(id_,[],['matrices'],{},6)['ranked']==[]


def test_semantic_and_hybrid_limits(fake_encoder):
    data=resources()
    lexical=recommend('tfidf',data,['recommandation'],{},3)
    embedded=recommend('embeddings',data,['recommandation'],{},3)
    assert embedded['effective_algorithm']=='embeddings'
    assert embedded['ranked'][0][0].id=='a'
    semantic_mmr=recommend('embeddings_mmr',data,['recommandation'],{},2,{'lambda':.2,'candidate_pool':3})
    assert [r.id for r,_ in semantic_mmr['ranked']]==['a','c']
    for alpha,reference in [(1,lexical),(0,embedded)]:
        hybrid=recommend('hybrid_content_mmr',data,['recommandation'],{},3,{'alpha':alpha,'lambda':1,'candidate_pool':3})
        assert [r.id for r,_ in hybrid['ranked']]==[r.id for r,_ in reference['ranked']]
        assert [score for _,score in hybrid['ranked']]==pytest.approx([score for _,score in reference['ranked']])


def test_model_missing_is_not_silently_replaced(monkeypatch):
    semantic.semantic_index.cache_clear()
    def missing(texts):
        raise ModelUnavailable('Modèle absent')
    monkeypatch.setattr(semantic.encoder,'encode',missing)
    for id_ in ['embeddings','embeddings_mmr','hybrid_content_mmr']:
        with pytest.raises(ModelUnavailable):
            recommend(id_,resources(),['recommandation'],{},2)


def test_admin_catalogue_sources_parameters_and_permissions(client,fake_encoder):
    catalogue=client.get('/algorithms').json()
    assert len([a for a in catalogue['algorithms'] if a['family']=='content'])==5
    assert not any('sources' in a for a in catalogue['algorithms'])
    assert client.get('/admin/algorithms').status_code==403
    assert client.get('/admin/algorithms/tfidf').status_code==403
    assert client.post('/admin/semantic-model/prepare').status_code==403
    with client.app.state.sessions() as db:
        db.scalar(select(User).where(User.email=='demo@example.com')).role='admin'
        db.commit()
    families=client.get('/admin/algorithms').json()['families']
    assert {f['id'] for f in families}=={'content','collaborative','filtering','hybrid','baselines'}
    paths=[]
    for id_ in ['tfidf','tfidf_mmr','embeddings','embeddings_mmr','hybrid_content_mmr']:
        detail=client.get('/admin/algorithms/'+id_).json()
        assert detail['formula'] and detail['steps'] and detail['limitations']
        paths.append(detail['sources'][0]['path'])
        assert 'class ' in detail['sources'][0]['content']
        result=client.post('/admin/algorithms/'+id_+'/preview',json={'interests':['collaboratif'],'limit':2})
        assert result.status_code==200
        assert result.json()['algorithm']==id_
        assert len(result.json()['items'])==2
    assert len(set(paths))==5
    assert client.post('/admin/algorithms/tfidf/preview',json={'parameters':{'lambda':.5}}).status_code==422
    assert client.post('/admin/algorithms/tfidf_mmr/preview',json={'limit':6,'parameters':{'candidate_pool':2}}).status_code==422
    assert client.post('/admin/algorithms/tfidf_mmr/preview',json={'parameters':{'lambda':2}}).status_code==422
    assert client.get('/admin/algorithms/unknown').status_code==404
    assert client.get('/recommendations?algorithm=unknown').status_code==404
    assert client.get('/recommendations?algorithm=tfidf&limit=0').status_code==422
    assert client.get('/me').json()['interests']==[]


def test_archived_and_unpublished_content_not_recommended(client,fake_encoder):
    from app.db import Course, Resource
    with client.app.state.sessions() as db:
        db.add(Course(id='hidden',title='Archive',description='',archived=True))
        db.flush()
        db.get(Resource,'video-1').course_id='hidden'
        db.get(Resource,'video-2').archived=True
        db.add(Resource(id='draft',title='Draft',description='',topic='test',level='test',kind='file',duration=0,url='',tags=[]))
        db.commit()
    client.patch('/me/profile',json={'interests':['recommandation']})
    for id_ in REGISTRY:
        response=client.get('/recommendations?algorithm='+id_)
        assert response.status_code==200
        assert [item['id'] for item in response.json()['items']]==['file-1']
