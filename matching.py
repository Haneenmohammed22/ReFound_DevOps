"""ReFound matching engine. Optional multilingual semantic embeddings, deterministic lexical fallback."""
import math
import os
import re
import unicodedata
from collections import Counter
from datetime import date
from difflib import SequenceMatcher

# A few domain translations improve the offline baseline; the optional model handles meaning much better.
CONCEPTS = {
 'سلسله':'necklace','سلسلة':'necklace','عقد':'necklace','necklace':'necklace','chain':'necklace','قلاده':'necklace','قلادة':'necklace',
 'ذهب':'gold','دهب':'gold','ذهبي':'gold','ذهبيه':'gold','golden':'gold','gold':'gold','اصفر':'yellow','صفراء':'yellow','yellow':'yellow',
 'سماعه':'earbuds','سماعة':'earbuds','سماعات':'earbuds','ايربودز':'earbuds','ايربود':'earbuds','headphones':'earbuds','earphones':'earbuds','earbuds':'earbuds',
 'محفظه':'wallet','محفظة':'wallet','wallet':'wallet','مفاتيح':'keys','مفتاح':'keys','keys':'keys',
 'شنطه':'bag','شنطة':'bag','حقيبه':'bag','حقيبة':'bag','bag':'bag','هاتف':'phone','موبايل':'phone','تليفون':'phone','جوال':'phone',
 'خاتم':'ring','دبله':'ring','دبلة':'ring','ring':'ring','ساعة':'watch','ساعه':'watch','watch':'watch',
 'كارت':'card','بطاقه':'card','بطاقة':'card','card':'card','هوية':'idcard','كارنيه':'idcard','id':'idcard',
 'لاب':'laptop','لابتوب':'laptop','كمبيوتر':'laptop','laptop':'laptop',
 'اسود':'black','سوداء':'black','سودا':'black','black':'black','ابيض':'white','بيضاء':'white','white':'white',
 'احمر':'red','حمراء':'red','red':'red','ازرق':'blue','زرقاء':'blue','blue':'blue','اخضر':'green','خضراء':'green','green':'green',
 'مكتبه':'library','مكتبة':'library','library':'library','كافتيريا':'cafeteria','كافيتريا':'cafeteria','cafeteria':'cafeteria',
 'كليه':'faculty','كلية':'faculty','مدرج':'hall','قاعه':'hall','قاعة':'hall','بوابه':'gate','بوابة':'gate','معمل':'lab',
 'لاسلكي':'wireless','لاسلكيه':'wireless','لاسلكية':'wireless','wireless':'wireless','بلوتوث':'bluetooth','bluetooth':'bluetooth',
}
STOPWORDS = {'the','a','an','my','i','lost','found','near','at','in','it','this','that','was','is', 'من','في','انا','لقيت','لقيتها','ضاعت','ضاع','عندي','على','علي','بجانب','جنب','تم','العثور','عن','شيء','حاجه','حاجة','لونها','لونه','بتاعتي','بتاعي'}

_model = None
_model_checked = False

def normalize(text):
    text = unicodedata.normalize('NFKC', str(text or '').lower())
    text = re.sub('[\u064b-\u065f\u0670\u0640]', '', text)
    text = text.translate(str.maketrans('أإآىةؤئ','ااايهوي'))
    return re.sub(r'[^\w\s]', ' ', text)

def tokens(text):
    result=[]
    for raw in normalize(text).split():
        if raw in STOPWORDS: continue
        word=raw
        # Conservative Arabic definite-article stripping: only if it reveals a known concept.
        if word.startswith('ال') and len(word)>4 and word[2:] in CONCEPTS:
            word=word[2:]
        mapped=CONCEPTS.get(word,word)
        if len(mapped)>1 and mapped not in STOPWORDS: result.append(mapped)
    return result

def lexical(a,b):
    x,y=set(tokens(a)),set(tokens(b))
    if not x or not y: return 0.0
    # Dice coefficient on unique concepts, robust to verbose descriptions.
    return 2*len(x&y)/(len(x)+len(y))

def semantic_model():
    global _model,_model_checked
    if _model_checked: return _model
    _model_checked=True
    if os.getenv('REFOUND_ENABLE_SEMANTIC') != '1': return None
    try:
        from sentence_transformers import SentenceTransformer
        _model=SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')
    except Exception:
        _model=None
    return _model

def text_scores(source, candidates):
    a=source['title']+' '+source['description']
    others=[r['title']+' '+r['description'] for r in candidates]
    baseline=[lexical(a,b) for b in others]
    model=semantic_model()
    if model is None: return baseline,'lexical'
    try:
        from sentence_transformers import util
        vectors=model.encode([a]+others,convert_to_tensor=True,normalize_embeddings=True)
        sim=util.cos_sim(vectors[0],vectors[1:])[0].tolist()
        # Clamp raw cosine: mapping (cos+1)/2 misleadingly inflates weak matches.
        # Blend with domain-aware lexical tokens for short bilingual item descriptions.
        return [min(1.,max(0.,.78*max(0.,float(v))+.22*baseline[i])) for i,v in enumerate(sim)], 'semantic'
    except Exception:
        return baseline,'lexical'

def score_matches(source, candidates):
    if not candidates: return [], 'lexical'
    descriptions,mode=text_scores(source,candidates)
    result=[]
    for target,description_score in zip(candidates,descriptions):
        category=lexical(source['category'],target['category'])
        color=lexical(source['color'],target['color'])
        place=lexical(source['location'],target['location'])
        try:
            delta=abs((date.fromisoformat(source['event_date'])-date.fromisoformat(target['event_date'])).days)
            time=max(0.,1.-delta/30.)
        except (ValueError,TypeError): time=0.
        total=(.50*description_score+.17*category+.10*color+.13*place+.10*time)
        # Scale is a weighted similarity score, not ownership confidence.
        reasons=[]
        if category>=.6: reasons.append('category')
        if color>=.6: reasons.append('color')
        if place>=.5: reasons.append('location')
        if time>=.8: reasons.append('date')
        if description_score>=.55: reasons.append('description')
        # Decision Tree is an independent, advisory classifier, not a replacement
        # for the existing ranking score and not a proof of ownership.
        from decision_tree import classify_pair
        tree_result = classify_pair(source, target, description_score)
        result.append({'report':dict(target),'score':round(total*100),
                       'reasons':reasons, 'decision_tree':tree_result})
    result.sort(key=lambda v:(-v['score'],-v['report']['id']))
    return result,mode
