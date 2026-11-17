import {useState} from "react";
import type {Payment} from "./types";
import {utc} from "./common";
export function money(n:number,c:string){return new Intl.NumberFormat(undefined,{style:"currency",currency:c}).format(n)}
export function Ledger({rows}:{rows:Payment[]}){
 const [open,select]=useState(""),[notice,notify]=useState("");
 return <div className="ledger"><small>RECEIPT LEDGER / API RECORDS</small>{rows.map(p=><article key={p.id}><div><button className="receipt" aria-expanded={open===p.id} onClick={()=>select(open===p.id?"":p.id)}><code>{p.id}</code><strong>{money(p.amount,p.currency)}</strong><time>{utc(p.created_at)}</time><b className={p.status==="SUCCESS"?"verified":""}>{p.status}</b></button><button onClick={async()=>{try{await navigator.clipboard.writeText(p.id);notify("Copied "+p.id)}catch{notify("Copy unavailable; select the receipt ID to copy manually.")}}}>Copy UUID</button></div>{open===p.id&&<pre>{JSON.stringify(p,null,2)}</pre>}</article>)}<span role="status">{notice}</span></div>
}
