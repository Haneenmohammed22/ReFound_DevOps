"""Small, transparent offline retrieval benchmark — not a production accuracy claim."""
from matching import score_matches

def item(i, kind, title, category, color, location, day='2026-10-25'):
    return {'id':i,'kind':kind,'title':title,'description':title,
            'category':category,'color':color,'location':location,'event_date':day}

# Manually constructed bilingual pairs. Positive ID marks intended relevant candidate.
CASES=[
 (item(1,'lost','سلسلة ذهب','مجوهرات','ذهبي','مكتبة'), [item(11,'found','gold necklace','jewelry','gold','library'),item(12,'found','black headphones','electronics','black','gate')],11),
 (item(2,'lost','سماعة سوداء','إلكترونيات','اسود','مكتبة'), [item(21,'found','black earbuds','electronics','black','library'),item(22,'found','gold ring','jewelry','gold','cafeteria')],21),
 (item(3,'lost','محفظة سوداء','متعلقات','اسود','بوابة'), [item(31,'found','black wallet','متعلقات','black','gate'),item(32,'found','blue watch','مجوهرات','ازرق','معمل')],31),
 (item(4,'lost','موبايل ازرق','إلكترونيات','ازرق','معمل'), [item(41,'found','blue phone','electronics','blue','lab'),item(42,'found','gold necklace','jewelry','gold','library')],41),
 (item(5,'lost','خاتم ذهب','مجوهرات','ذهبي','كافتيريا'), [item(51,'found','gold ring','jewelry','gold','cafeteria'),item(52,'found','black bag','bags','black','gate')],51),
 (item(6,'lost','بطاقة هوية','وثائق','ابيض','مكتبة'), [item(61,'found','id card','وثائق','white','library'),item(62,'found','black earbuds','electronics','black','gate')],61),
 (item(7,'lost','ساعة سوداء','إكسسوارات','اسود','قاعة'), [item(71,'found','black watch','إكسسوارات','black','hall'),item(72,'found','gold necklace','مجوهرات','gold','library')],71),
 (item(8,'lost','مفاتيح','مفاتيح','فضي','بوابة'), [item(81,'found','keys','مفاتيح','فضي','gate'),item(82,'found','blue phone','electronics','blue','lab')],81),
]

def evaluate():
    correct=0; details=[]
    for source, candidates, expected in CASES:
        results,mode=score_matches(source,candidates)
        top=results[0]['report']['id'] if results else None
        correct+=top==expected
        details.append((source['title'],top,expected,mode))
    return correct,len(CASES),details

if __name__ == '__main__':
    correct,total,details=evaluate()
    for title,top,expected,mode in details:
        print(f'{"PASS" if top==expected else "FAIL"}: {title} (top={top}, expected={expected}; mode={mode})')
    print(f'Top-1 retrieval on {total} handcrafted cases: {correct}/{total} ({correct/total:.0%})')
    print('CAUTION: Tiny curated examples; NOT generalizable accuracy or ownership probability.')
