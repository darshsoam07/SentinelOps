import {ThemeSelect} from "./ThemeSelect";
import {useEffect,useState} from "react";
import {useQueryClient,useIsFetching} from "@tanstack/react-query";
import {AudioWaveform} from "lucide-react";
import {setToken} from "./services/api";
import {usePayments} from "./hooks/usePayments";
import Overview from "./pages/Overview";
import Payflow from "./pages/Payflow";
import {money} from "./ReceiptLedger";
export function CommandBar(){
 const [now,tick]=useState(()=>new Date()),client=useQueryClient(),pending=useIsFetching();
 useEffect(()=>{const id=setInterval(()=>tick(new Date()),1000);return ()=>clearInterval(id)},[]);
 return <header className="commandbar"><AudioWaveform aria-hidden="true"/><i/><b>SNT-001 // COMMAND PLANE</b><span title="Schema target">OPS DB: 0002 HEAD</span><ThemeSelect/><time>{now.toISOString().slice(11,19)} UTC</time><span>Authenticated operator</span><button disabled={!!pending} onClick={()=>void client.refetchQueries({type:"active"})}>Sync Telemetry</button><button onClick={()=>setToken("")}>Sign out</button></header>
}
export default function SentinelOpsDashboard(){
 const payments=usePayments(),totals=new Map<string,number>();
 for(const p of payments.data??[])if(p.status==="SUCCESS")totals.set(p.currency,(totals.get(p.currency)??0)+Math.round(p.amount*100));
 const tiles=[["Cluster node","SNT-001","ONLINE · 99.998% SLA"],["PayFlow engine","HTTP 201 READY","12.4ms p95"],["Settled volume",payments.data?Array.from(totals,([c,n])=>money(n/100,c)).join(" / ")||"0": "—","Successful loaded receipts"],["Alembic & DB state","REV 0002 (HEAD)","ASYNC POOL HEALTHY"]];
 return <><small className="eyeline">MISSION CONTROL / LOCAL WORKSPACE</small><h1>Operations overview</h1><div className="kpis">{tiles.map(([label,value,detail],i)=><section key={label}><small>{label} {i!==2&&" / DEMO"}</small><strong>{value}</strong><code>{detail}</code>{i<2&&<svg viewBox="0 0 130 18" aria-hidden="true"><path d={i===0?"M0 15h12V8h4v7h9V4h5v11h11V7h4v8h14V3h5v12h11V6h4v9h20V8h5v7h26":"M0 12l14 -2 9 3 10 -8 12 5 7 -2 11 3 11 -9 7 8 13 -3 10 3 15 -5 11 3"} fill="none" stroke="currentColor"/></svg>}</section>)}</div><div className="opsgrid"><div><Overview/></div><Payflow embedded/></div></>
}
