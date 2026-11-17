const API=(import.meta as any).env.VITE_API_URL || '';
let csrf='';
export function setCsrf(value:string){csrf=value;}
export async function api(path:string,options:RequestInit={}){
 const response=await fetch(API+'/api'+path,{...options,credentials:'include',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf,...options.headers}});
 const data=await response.json().catch(()=>({detail:'The server returned an unexpected response'}));
 if(!response.ok)throw data.detail||'Request failed';return data;
}
export async function download(kind:string,year:number,month:number){
 const r=await fetch(`${API}/api/export/${kind}?year=${year}&month=${month}`,{credentials:'include'});
 if(!r.ok)throw new Error('Export failed. Please sign in again.');
 const url=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=url;a.download=`nutripulse-${year}-${month}.${kind}`;a.click();URL.revokeObjectURL(url);
}
