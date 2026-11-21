"""Ranking validation and penalty sensitivity. Run from project root: python src/run_c_step3.py"""
from pathlib import Path
import argparse,csv,hashlib,json,sys,time,os,importlib
import numpy as np
SCRIPT_DIR=Path(__file__).resolve().parent
# Original step-2 project remains the source of shared code/data/results.
ROOT=Path(os.environ.get('HEFEI_PROJECT_DIR',str(SCRIPT_DIR.parent))).resolve()
required=[ROOT/'src/build_network.py',ROOT/'src/routing.py',ROOT/'data/processed',ROOT/'reference',ROOT/'results/tables/c/step2']
missing=[str(p) for p in required if not p.exists()]
if missing:
    raise FileNotFoundError('第二步项目缺少文件或目录：'+ '; '.join(missing)+'。请保留同级C第二步_多站中断文件夹，或设置HEFEI_PROJECT_DIR。')
os.environ['HEFEI_DATA_DIR']=str(ROOT/'data/processed')
sys.path.insert(0,str(ROOT/'src'))
bn=importlib.import_module('build_network')
rt=importlib.import_module('routing')
PENALTIES=[0,1,2,3,5]
STRATEGIES=['random','centrality','single_loss']
METRICS=['unreachable_ratio','mean_delta_survivors','mean_delta_affected','efficiency_ratio']
LABELS=['随机中断','原始介数排名','基准单站损失排名']
COLORS=['#168b91','#19384c','#d39838']
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def rank(v):
    order=sorted(range(len(v)),key=lambda i:-v[i]);r=[0.]*len(v);i=0
    while i<len(v):
        j=i+1
        while j<len(v) and v[order[j]]==v[order[i]]:j+=1
        for z in range(i,j):r[order[z]]=(i+1+j)/2
        i=j
    return r
def rho(a,b):
    x=rank(a);y=rank(b)
    return float(np.corrcoef(x,y)[0,1]) if np.std(x)>0 and np.std(y)>0 else None
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repeats',type=int,default=100)
    ap.add_argument('--step2',default='results/tables/c/step2')
    ap.add_argument('--output',default='results/tables/c/step3')
    args=ap.parse_args()
    if args.repeats<1:ap.error('repeats must be positive')
    out=ROOT/args.output;out.mkdir(parents=True,exist_ok=True)
    source=ROOT/args.step2
    files=[source/'C01_disruption_orders.csv',source/'C02_multi_disruption_detail.csv',source/'C05_run_parameters.json',ROOT/'reference/B02_transfer_station_ranking.csv',ROOT/'reference/B04_single_transfer_disruption.csv']
    orders=read(files[0]);old=read(files[1]);params=json.loads(files[2].read_text(encoding='utf-8-sig'))
    if params['transfer_penalty']!=2:raise ValueError('Step 2 penalty must be 2')
    for rel,h in params['hashes'].items():
        rel=rel.replace('\\','/')
        if rel.startswith(('data/','reference/')) or rel in ['src/build_network.py','src/routing.py']:
            if hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()!=h:raise ValueError('Input changed: '+rel)
    grouped={}
    for row in orders:
        s=row['strategy'];t=int(row['trial'])
        if s not in STRATEGIES:raise ValueError('Unknown strategy')
        if s=='random' and t>args.repeats:continue
        grouped.setdefault((s,t),[]).append((int(row['position']),row['station']))
    schedules=[(s,t,[v for k,v in sorted(rows)]) for (s,t),rows in sorted(grouped.items())]
    if {t for s,t,o in schedules if s=='random'}!=set(range(1,args.repeats+1)):raise ValueError('Not enough step-2 random trials')
    if not all((s,0) in grouped for s in ['centrality','single_loss']):raise ValueError('Targeted sequences missing')
    g=bn.build_multilayer_network();stations=sorted(bn.transfer_station_names(g))
    if len(stations)!=19:raise ValueError('Expected 19 transfer stations')
    for s,t,o in schedules:
        if len(o)!=19 or set(o)!=set(stations):raise ValueError('Invalid order')
    central={r['station']:float(r['betweenness_centrality']) for r in read(files[3])}
    b_loss={r['station']:float(r['loss_index']) for r in read(files[4])}
    lookup={(r['strategy'],int(r['trial']),int(r['k'])):r for r in old}
    fingerprints={(str(f.relative_to(ROOT)) if f.is_relative_to(ROOT) else 'external/'+f.name):hashlib.sha256(f.read_bytes()).hexdigest() for f in files+[Path(__file__),ROOT/'src/build_network.py',ROOT/'src/routing.py']+sorted((ROOT/'data/processed').glob('*.csv'))}
    sig=hashlib.sha256(json.dumps(fingerprints,sort_keys=True).encode()).hexdigest()[:16]
    cf=out/('cache_'+sig+'.jsonl');cache={}
    if cf.exists():
        for line in cf.read_text(encoding='utf-8').splitlines():
            try:r=json.loads(line)
            except json.JSONDecodeError:continue
            cache[r['key']]=r['value']
    detail=[];single=[];start=time.perf_counter();n=18915
    for p in PENALTIES:
        model='c_penalty_'+str(p);rt.COST_MODELS[model]=p
        ev=rt.ODEvaluator(g,model=model);pairs=rt.all_od_pairs(ev.stations)
        if len(pairs)!=n:raise ValueError('OD count mismatch')
        base={pair:ev.evaluate_pair(*pair) for pair in pairs}
        if not all(r.reachable for r in base.values()):raise ValueError('Baseline disconnected')
        bm=sum(r.cost for r in base.values())/n;be=sum(1/r.cost for r in base.values())/n
        if p==2 and abs(bm-params['baseline_mean_cost'])>1e-9:raise ValueError('Baseline mismatch')
        def evaluate(closed):
            key=str(p)+'|'+ ';'.join(sorted(closed))
            if key in cache:return cache[key]
            graph,info=rt.build_cost_graph(g,model=model,closed_transfer_stations=closed)
            if len(graph)!=215 or info['running_edges']!=207:raise ValueError('Running graph changed')
            ev.set_graph(graph);lost=affected=0;delta=inv=0.
            for pair in pairs:
                a=ev.evaluate_pair(*pair)
                if not a.reachable:lost+=1;continue
                d=a.cost-base[pair].cost
                if d < -1e-9:raise ValueError('Cost decreased after closure')
                delta+=d;affected+=int(d>1e-9);inv+=1/a.cost
            survivors=n-lost
            v=dict(unreachable_ratio=lost/n,unreachable_od=lost,affected_od=affected,
                   mean_delta_survivors=delta/survivors if survivors else None,
                   mean_delta_affected=delta/affected if affected else None,
                   efficiency_ratio=(inv/n)/be,single_loss_index=(delta/n)/bm,
                   baseline_mean_cost=bm,baseline_efficiency=be)
            with cf.open('a',encoding='utf-8') as f:f.write(json.dumps(dict(key=key,value=v),ensure_ascii=False)+'\n')
            cache[key]=v;return v
        for station in stations:
            v=evaluate([station])
            if v['unreachable_od']!=0:raise ValueError('Singleton disconnected')
            if p==2 and abs(v['single_loss_index']-b_loss[station])>1e-6:raise ValueError('B singleton mismatch')
            single.append(dict(penalty=p,station=station,centrality=central[station],**v))
        print(f'换乘惩罚{p}：19座单站计算完成',flush=True)
        for idx,(s,t,order) in enumerate(schedules,1):
            previous=None
            for k in range(20):
                reference=lookup[(s,t,k)]
                if reference['closed_stations']!=';'.join(sorted(order[:k])):raise ValueError('Order mismatch')
                if p==2:
                    v={m:float(reference[m]) if reference[m] else None for m in METRICS}
                    v['unreachable_od']=int(reference['unreachable_od'])
                else:v=evaluate(order[:k])
                if v['unreachable_od']!=int(reference['unreachable_od']):raise ValueError('Penalty changed reachability')
                if previous and (v['unreachable_ratio']<previous['unreachable_ratio']-1e-10 or v['efficiency_ratio']>previous['efficiency_ratio']+1e-10):raise ValueError('Monotonicity failed')
                detail.append(dict(penalty=p,strategy=s,trial=t,k=k,**{m:v[m] for m in METRICS}));previous=v
            print(f'换乘惩罚{p}：序列{idx}/{len(schedules)}',flush=True)
    base_losses=[r['single_loss_index'] for r in single if r['penalty']==2]
    def top(v,k=5):return set(sorted(range(19),key=lambda i:(-v[i],stations[i]))[:k])
    cv=[central[s] for s in stations];rankrows=[];stability=[]
    for p in PENALTIES:
        rows=[r for r in single if r['penalty']==p];v=[r['single_loss_index'] for r in rows]
        cr=rank(cv);lr=rank(v);order=sorted(range(19),key=lambda i:(-v[i],stations[i]))
        for i,r in enumerate(rows):rankrows.append(dict(**r,centrality_rank=cr[i],loss_rank=lr[i],rank_difference=lr[i]-cr[i]))
        stability.append(dict(penalty=p,spearman_centrality_vs_loss=rho(cv,v),spearman_loss_vs_penalty2=rho(base_losses,v),top5_overlap_with_centrality=len(top(cv)&top(v)),top5_overlap_with_penalty2=len(top(base_losses)&top(v)),loss_top3=';'.join(stations[i] for i in order[:3]),loss_top5=';'.join(stations[i] for i in order[:5])))
    summary=[];auc=[];auc_summary=[]
    for p in PENALTIES:
        for s in STRATEGIES:
            for k in range(20):
                rows=[r for r in detail if r['penalty']==p and r['strategy']==s and r['k']==k]
                rec=dict(penalty=p,strategy=s,k=k,samples=len(rows))
                for m in METRICS:
                    v=[r[m] for r in rows if r[m] is not None];rec[m+'_valid_n']=len(v)
                    for suffix,z in [('mean',np.mean(v) if v else None),('p025',np.quantile(v,.025) if v else None),('p975',np.quantile(v,.975) if v else None)]:rec[m+'_'+suffix]=float(z) if z is not None else None
                summary.append(rec)
        for s,t,o in schedules:
            rows=sorted([r for r in detail if r['penalty']==p and r['strategy']==s and r['trial']==t],key=lambda r:r['k'])
            area=sum((rows[i]['efficiency_ratio']+rows[i+1]['efficiency_ratio'])/2/19 for i in range(19))
            auc.append(dict(penalty=p,strategy=s,trial=t,efficiency_auc=area))
        for s in STRATEGIES:
            v=[r['efficiency_auc'] for r in auc if r['penalty']==p and r['strategy']==s]
            auc_summary.append(dict(penalty=p,strategy=s,samples=len(v),auc_mean=float(np.mean(v)),auc_p025=float(np.quantile(v,.025)),auc_p975=float(np.quantile(v,.975))))
    for name,rows in [('C06_ranking_by_penalty.csv',rankrows),('C07_ranking_stability.csv',stability),('C08_sensitivity_detail.csv',detail),('C09_sensitivity_summary.csv',summary),('C10_efficiency_auc_detail.csv',auc),('C11_efficiency_auc_summary.csv',auc_summary)]:write(out/name,rows)
    (out/'C12_run_parameters.json').write_text(json.dumps(dict(version='C3-1.0',penalties=PENALTIES,repeats=args.repeats,orders='fixed step-2 orders across penalties',tied_ranks='average ranks for correlation; station name for top-k',penalty2='reused step2; baseline and singleton loss rechecked',hashes=fingerprints,seconds=time.perf_counter()-start),ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'results/figures/c').mkdir(parents=True,exist_ok=True)
    plots(rankrows,stability,summary,auc_summary,ROOT/'results/figures/c')
    print('完成：'+str(out),flush=True)
def plots(rankrows,stability,summary,auc,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif']=['Microsoft YaHei','SimHei','DejaVu Sans'];plt.rcParams['axes.unicode_minus']=False
    def save(fig,name):
        fig.tight_layout();fig.savefig(out/(name+'.png'),dpi=220);fig.savefig(out/(name+'.svg'));plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,8))
    for r in rankrows:
        if r['penalty']!=2:continue
        ax.scatter(r['centrality_rank'],r['loss_rank'],color=COLORS[0]);ax.annotate(r['station'],(r['centrality_rank'],r['loss_rank']),xytext=(4,4),textcoords='offset points',fontsize=9)
    ax.plot([1,19],[1,19],'--',color='gray',alpha=.5)
    ax.set(xlabel='介数排名（1最高）',ylabel='单站损失排名（1最高）',title='换乘惩罚2：结构与单站损失排名',xticks=range(1,20,2),yticks=range(1,20,2));ax.invert_yaxis();ax.grid(alpha=.15);save(fig,'C_fig5_rank_comparison')
    fig,ax=plt.subplots(figsize=(8,5))
    for key,label,c in [('spearman_loss_vs_penalty2','损失排名与惩罚2的相关性',COLORS[0]),('spearman_centrality_vs_loss','结构排名与损失排名相关性',COLORS[1])]:ax.plot(PENALTIES,[r[key] for r in stability],'-o',label=label,color=c)
    ax.set(xlabel='换乘惩罚（等效站）',ylabel='Spearman秩相关',ylim=(-1.05,1.05));ax.legend();ax.grid(alpha=.15);save(fig,'C_fig6_rank_stability')
    fig,axes=plt.subplots(1,5,figsize=(20,4.8),sharex=True,sharey=True)
    for ax,p in zip(axes,PENALTIES):
        for s,label,c in zip(STRATEGIES,LABELS,COLORS):
            rows=[r for r in summary if r['penalty']==p and r['strategy']==s];x=[r['k'] for r in rows]
            ax.plot(x,[r['efficiency_ratio_mean'] for r in rows],color=c,label=label)
            if s=='random':ax.fill_between(x,[r['efficiency_ratio_p025'] for r in rows],[r['efficiency_ratio_p975'] for r in rows],color=c,alpha=.15)
        ax.set(title='换乘惩罚='+str(p),xlabel='关闭换乘站数量',xticks=[0,5,10,15,19]);ax.grid(alpha=.15)
    axes[0].set_ylabel('相对各参数自身基线的OD效率');axes[-1].legend(fontsize=8);save(fig,'C_fig7_efficiency_sensitivity')
    fig,ax=plt.subplots(figsize=(8,5))
    for s,label,c in zip(STRATEGIES,LABELS,COLORS):
        rows=[r for r in auc if r['strategy']==s];ax.plot(PENALTIES,[r['auc_mean'] for r in rows],'-o',label=label,color=c)
    ax.set(xlabel='换乘惩罚（等效站）',ylabel='效率曲线面积（越小破坏越强）');ax.legend();ax.grid(alpha=.15);save(fig,'C_fig8_auc_sensitivity')
if __name__=='__main__':main()
