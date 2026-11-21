"""C step 2: multi-station transfer disruption; run from any working directory."""
from pathlib import Path
import argparse, csv, hashlib, json, random, sys, time
import numpy as np
import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import build_network as bn
import routing as rt

VERSION = 'C2-1.0'
STRATEGIES = ('random', 'centrality', 'single_loss')
LABELS = {'random': '随机中断', 'centrality': '原始介数排名', 'single_loss': '原始单站损失排名'}
METRICS = ['unreachable_ratio', 'mean_delta_survivors', 'mean_delta_affected',
           'mean_extra_rides_survivors', 'mean_extra_transfers_survivors',
           'efficiency_ratio', 'affected_ratio']

def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def write_csv(path, rows):
    if not rows:
        raise ValueError('Empty output: ' + str(path))
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def evaluate(g, ev, pairs, baseline, closed, base_eff):
    graph, info = rt.build_cost_graph(g, closed_transfer_stations=closed)
    if info['running_edges'] != 207 or len(graph) != 215:
        raise RuntimeError('Disruption changed running edges or nodes')
    ev.set_graph(graph)
    lost = affected = survivors = 0
    delta = rides = transfers = inv = 0.0
    for o, d in pairs:
        before = baseline[(o, d)]
        after = ev.evaluate_pair(o, d)
        if not after.reachable:
            lost += 1; continue
        survivors += 1
        change = after.cost - before.cost
        if change < -1e-9:
            raise RuntimeError('Removing transfer connections reduced shortest-path cost')
        if change > 1e-9:
            affected += 1
        delta += change
        rides += after.rides - before.rides
        transfers += after.transfers - before.transfers
        inv += 1.0 / after.cost
    n = len(pairs)
    return dict(closed_stations=';'.join(sorted(closed)), closed_count=len(closed),
                closed_transfer_edges=21-info['transfer_edges'], od_pairs=n,
                reachable_od=survivors, unreachable_od=lost, affected_od=affected,
                unreachable_ratio=lost/n, affected_ratio=affected/n,
                mean_delta_survivors=delta/survivors if survivors else None,
                mean_delta_affected=delta/affected if affected else None,
                mean_extra_rides_survivors=rides/survivors if survivors else None,
                mean_extra_transfers_survivors=transfers/survivors if survivors else None,
                # Signed changes: extra transfers can be negative after rerouting.
                mean_delta_all_od_excluding_lost=delta/n,
                efficiency=inv/n, efficiency_ratio=(inv/n)/base_eff)

def plots(summary, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    colors = {'random': '#168b91', 'centrality': '#19384c', 'single_loss': '#d39838'}
    specs = [('unreachable_ratio', '不可达OD比例', 'C_fig1_unreachable'),
             ('mean_delta_survivors', '全部仍可达OD平均增量（等效站）', 'C_fig2_survivor_cost'),
             ('efficiency_ratio', '相对基线的物理OD效率', 'C_fig3_efficiency'),
             ('mean_delta_affected', '代价增加OD平均增量（等效站）', 'C_fig4_affected_cost')]
    for metric, label, name in specs:
        fig, ax = plt.subplots(figsize=(9, 5.2))
        for strategy in STRATEGIES:
            rows = [r for r in summary if r['strategy'] == strategy]
            x = [r['k'] for r in rows]
            y = [r[metric+'_mean'] for r in rows]
            y = [np.nan if v is None else v for v in y]
            ax.plot(x, y, label=LABELS[strategy], color=colors[strategy], lw=2)
            if strategy == 'random':
                low = [np.nan if r[metric+'_p025'] is None else r[metric+'_p025'] for r in rows]
                high = [np.nan if r[metric+'_p975'] is None else r[metric+'_p975'] for r in rows]
                ax.fill_between(x, low, high, color=colors[strategy], alpha=.17,
                                label='随机结果2.5%—97.5%分位区间')
        ax.set(xlabel='关闭换乘功能的物理站数量', ylabel=label, xticks=range(0,20,2))
        ax.spines[['top','right']].set_visible(False)
        ax.grid(alpha=.16); ax.legend(fontsize=9)
        fig.text(.5,.015,'1—8号线；18,915对等权物理OD；换乘惩罚2等效站；仅关闭换乘连接',ha='center',fontsize=9)
        fig.tight_layout(rect=(0,.05,1,1))
        fig.savefig(out/(name+'.png'), dpi=220)
        fig.savefig(out/(name+'.svg'))
        plt.close(fig)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repeats', type=int, default=100)
    ap.add_argument('--seed', type=int, default=20261116)
    ap.add_argument('--output', default='results/tables/c/step2')
    args = ap.parse_args()
    if args.repeats < 1: ap.error('--repeats must be >= 1')
    out = ROOT/args.output; out.mkdir(parents=True,exist_ok=True)
    started = time.perf_counter()
    g = bn.build_multilayer_network()
    info = bn.network_summary(g)
    if (info['physical_stations'],len(g),info['running_edges'],info['candidate_transfer_edges']) != (195,215,207,21):
        raise RuntimeError('Input network differs from verified baseline')
    central = read_csv(ROOT/'reference/B02_transfer_station_ranking.csv')
    losses = read_csv(ROOT/'reference/B04_single_transfer_disruption.csv')
    central_order = [r['station'] for r in sorted(central,key=lambda r:(-float(r['betweenness_centrality']),r['station']))]
    loss_order = [r['station'] for r in sorted(losses,key=lambda r:(-float(r['loss_index']),r['station']))]
    stations = sorted(bn.transfer_station_names(g))
    if len(stations)!=19 or set(central_order)!=set(stations) or set(loss_order)!=set(stations):
        raise RuntimeError('Ranking station set mismatch')
    fingerprints={}
    for path in sorted((ROOT/'data/processed').glob('*.csv'))+sorted((ROOT/'reference').glob('*'))+sorted((ROOT/'src').glob('*.py')):
        fingerprints[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    signature=hashlib.sha256(json.dumps([VERSION,fingerprints],sort_keys=True).encode()).hexdigest()
    cache_path=out/('cache_'+signature[:16]+'.jsonl')
    cache={}
    if cache_path.exists():
        for line in cache_path.read_text(encoding='utf-8').splitlines():
            try: rec=json.loads(line)
            except json.JSONDecodeError: continue
            cache[rec['key']]=rec['value']
    ev=rt.ODEvaluator(g)
    pairs=rt.all_od_pairs(ev.stations)
    baseline={pair:ev.evaluate_pair(*pair) for pair in pairs}
    if not all(r.reachable for r in baseline.values()): raise RuntimeError('Baseline disconnected')
    base_eff=sum(1/r.cost for r in baseline.values())/len(pairs)
    base_mean=sum(r.cost for r in baseline.values())/len(pairs)
    if abs(base_mean-17.356436690457308)>1e-9: raise RuntimeError('B baseline mean mismatch')
    def get(closed):
        key=';'.join(sorted(closed))
        if key not in cache:
            value=evaluate(g,ev,pairs,baseline,closed,base_eff)
            with cache_path.open('a',encoding='utf-8') as f:
                f.write(json.dumps({'key':key,'value':value},ensure_ascii=False)+'\n')
            cache[key]=value
        return cache[key]
    # Singleton checks validate the data handoff before any new experiment.
    for i, row in enumerate(losses,1):
        v=get([row['station']])
        if v['unreachable_od']!=int(row['lost_od']) or v['affected_od']!=int(row['detour_od']) or abs(v['mean_delta_all_od_excluding_lost']-float(row['mean_detour_all_od']))>1e-6:
            raise RuntimeError('Single-station B check failed: '+row['station'])
        print(f'B复核 {i}/19：{row["station"]}',flush=True)
    schedules=[('centrality',0,central_order),('single_loss',0,loss_order)]
    rng=random.Random(args.seed)
    for trial in range(1,args.repeats+1):
        order=stations.copy(); rng.shuffle(order)
        schedules.append(('random',trial,order))
    orders=[]; detail=[]
    for idx,(strategy,trial,order) in enumerate(schedules,1):
        for pos,station in enumerate(order,1):
            orders.append(dict(strategy=strategy,trial=trial,position=pos,station=station))
        previous=None
        for k in range(20):
            value=get(order[:k])
            if previous and (value['unreachable_od']<previous['unreachable_od'] or value['efficiency']>previous['efficiency']+1e-10):
                raise RuntimeError('Nested disruption monotonicity check failed')
            detail.append(dict(strategy=strategy,trial=trial,k=k,**value));previous=value
        print(f'实验序列 {idx}/{len(schedules)}；已缓存 {len(cache)} 个不同中断集合',flush=True)
    summary=[]
    for strategy in STRATEGIES:
        for k in range(20):
            group=[r for r in detail if r['strategy']==strategy and r['k']==k]
            rec=dict(strategy=strategy,k=k,samples=len(group))
            for metric in METRICS:
                values=[r[metric] for r in group if r[metric] is not None]
                rec[metric+'_valid_n']=len(values)
                for suffix, val in [('mean',np.mean(values) if values else None),('p025',np.quantile(values,.025) if values else None),('p975',np.quantile(values,.975) if values else None)]:
                    rec[metric+'_'+suffix]=float(val) if val is not None else None
            summary.append(rec)
    write_csv(out/'C01_disruption_orders.csv',orders)
    write_csv(out/'C02_multi_disruption_detail.csv',detail)
    write_csv(out/'C03_multi_disruption_summary.csv',summary)
    areas=[]
    for strategy,trial,_ in schedules:
        rows=[r for r in detail if r['strategy']==strategy and r['trial']==trial]
        # Trapezoidal area over fraction closed [0,1], without requiring recent NumPy.
        auc=sum((rows[i]['efficiency_ratio']+rows[i+1]['efficiency_ratio'])/2/19 for i in range(19))
        areas.append(dict(strategy=strategy,trial=trial,efficiency_auc=auc))
    write_csv(out/'C04_efficiency_auc.csv',areas)
    parameters=dict(version=VERSION,network=info,repeats=args.repeats,seed=args.seed,
                    transfer_penalty=2,od_pairs=len(pairs),baseline_mean_cost=base_mean,
                    baseline_efficiency=base_eff,ranking='fixed original, ties by station name',
                    random_band='empirical 2.5% to 97.5% quantiles, not a confidence interval',
                    hashes=fingerprints,seconds=time.perf_counter()-started)
    (out/'C05_run_parameters.json').write_text(json.dumps(parameters,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'results/figures/c').mkdir(parents=True,exist_ok=True)
    plots(summary, ROOT/'results/figures/c')
    print('完成。结果目录：'+str(out),flush=True)

if __name__=='__main__':
    main()
