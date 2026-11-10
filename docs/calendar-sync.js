const weekdays=["Lunedì","Martedì","Mercoledì","Giovedì","Venerdì","Sabato","Domenica"];
const calKey="scooterCalendarV1";
let calendar=[];
try{const x=JSON.parse(localStorage.getItem(calKey)||"[]");if(Array.isArray(x))calendar=x}catch(e){}
let editingTrip=null,sessionToken=null,syncTimer=null;
function renderCalendarSelectors(){
 const fav=$("calFavorite"),selected=fav.value;
 fav.replaceChildren();
 const empty=document.createElement("option");empty.value="";empty.textContent="Scegli un percorso salvato…";fav.append(empty);
 favorites.forEach((route,i)=>{if(!regions[route.from]||!regions[route.to])return;const o=document.createElement("option");o.value=String(i);o.textContent=route.from+" → "+route.to;fav.append(o)});
 if(selected&&[...fav.options].some(o=>o.value===selected))fav.value=selected;

 for(const id of ["calFrom","calTo"]){
  const el=$(id),old=el.value;el.replaceChildren();
  Object.keys(regions).forEach(k=>{const o=document.createElement("option");o.value=k;o.textContent=k;el.append(o)});
  el.value=regions[old]?old:id==="calFrom"?"casa":"fisica";
 }
}
$("calFavorite").onchange=()=>{
 const item=favorites[Number($("calFavorite").value)];
 if($("calFavorite").value!==""&&item){$("calFrom").value=item.from;$("calTo").value=item.to}
};
weekdays.forEach((name,i)=>{const o=document.createElement("option");o.value=i;o.textContent=name;$("calDay").append(o)});
function persistCalendar(){localStorage.setItem(calKey,JSON.stringify(calendar));renderCalendar();queueSync()}
function renderCalendar(){
 const root=$("calendar");root.replaceChildren();
 const fullResults=document.createElement("div");fullResults.className="calendar-full-results";fullResults.hidden=true;
 weekdays.forEach((day,i)=>{
  const col=document.createElement("div");col.className="calendar-day";
  const title=document.createElement("h4");title.textContent=day;col.append(title);
  calendar.filter(t=>t.day===i).sort((a,b)=>a.time.localeCompare(b.time)).forEach(t=>{
   const card=document.createElement("div");card.className="calendar-trip";
   const label=document.createElement("div");label.textContent=t.time+" · "+t.from+" → "+t.to;card.append(label);
   const edit=document.createElement("button");edit.textContent="✏️";edit.title="Modifica";edit.onclick=()=>{
    editingTrip=t.id;renderCalendarSelectors();$("calDay").value=t.day;$("calTime").value=t.time;$("calFrom").value=t.from;$("calTo").value=t.to;$("calFavorite").value="";
    $("calDialogTitle").textContent="✏️ Modifica tragitto";$("calSave").textContent="Salva modifica";$("calDialog").showModal();
   };
   const remove=document.createElement("button");remove.textContent="×";remove.title="Elimina";remove.onclick=()=>{calendar=calendar.filter(x=>x.id!==t.id);persistCalendar()};
   card.append(edit,remove);col.append(card);
  });
  const trips=calendar.filter(t=>t.day===i).sort((a,b)=>a.time.localeCompare(b.time));
  if(trips.length){
   const button=document.createElement("button");button.type="button";button.textContent="🛵 Calcola il tragitto";button.style.cssText="width:100%;margin-top:10px;padding:9px 5px;font-size:12px";
   const results=fullResults;
   button.onclick=async()=>{
    if(!results.hidden&&results.dataset.day===String(i)){results.hidden=true;button.textContent="🛵 Calcola il tragitto";return}
    root.querySelectorAll(".calendar-day button").forEach(b=>{if(b.textContent==="🔼 Nascondi tragitti")b.textContent="🛵 Calcola il tragitto"});
    results.dataset.day=String(i);
    results.hidden=false;results.replaceChildren();button.disabled=true;button.textContent="⏳ Calcolo…";
    try{
     const today=new Date(),offset=(i-(today.getDay()+6)%7+7)%7;
     const target=new Date(today.getFullYear(),today.getMonth(),today.getDate()+offset);
     const date=target.getFullYear()+"-"+String(target.getMonth()+1).padStart(2,"0")+"-"+String(target.getDate()).padStart(2,"0");
     const heading=document.createElement("p");heading.textContent="📅 "+target.toLocaleDateString("it-IT",{weekday:"long",day:"numeric",month:"long"});results.append(heading);
     for(const trip of trips){
      const section=document.createElement("section");section.className="calendar-route-result";
      const title=document.createElement("h4");title.textContent=trip.time+" · "+trip.from+" → "+trip.to;
      const out=document.createElement("div");section.append(title,out);results.append(section);
      if(!regions[trip.from]||!regions[trip.to]){out.textContent="Tappa non disponibile";continue}
      await calculateScooterTrip(trip.from,trip.to,date,trip.time,out);
     }
    }finally{button.disabled=false;button.textContent="🔼 Nascondi tragitti"}
   };
   col.append(button);
  }
  root.append(col);
 });
 root.after(fullResults);
}

const weeklyRouteCache=new Map();
$("calConsumption").addEventListener("click",async()=>{
 const button=$("calConsumption"),out=$("calConsumptionResult");
 out.hidden=false;out.textContent="Calcolo delle distanze stradali dei tragitti settimanali…";
 button.disabled=true;
 try{
  const consumption=Number(fuelInput.value);
  if(!Number.isFinite(consumption)||consumption<1||consumption>15)throw Error("Imposta un consumo valido tra 1 e 15 L/100 km nella sezione Benzina.");
  const price=fuelData?.price_eur_l;
  const byDay=Array(7).fill(0),failed=[];
  const routes=new Map();
  for(const trip of calendar){
   if(!Number.isInteger(trip.day)||trip.day<0||trip.day>6)continue;
   if(!regions[trip.from]||!regions[trip.to]){
    failed.push(weekdays[trip.day]+": tappa mancante ("+trip.from+" → "+trip.to+")");continue;
   }
   const key=JSON.stringify([regions[trip.from],regions[trip.to]]);
   if(!routes.has(key))routes.set(key,{from:trip.from,to:trip.to});
  }
  const distances=new Map();
  for(const [key,route] of routes){
   try{
    if(!weeklyRouteCache.has(key)){
     const a=await geo(regions[route.from]),b=await geo(regions[route.to]);
     const url="https://router.project-osrm.org/route/v1/driving/"+a[1]+","+a[0]+";"+b[1]+","+b[0]+"?overview=false";
     const data=await api(url,"OSRM (distanze calendario)");
     const meters=Number(data.routes?.[0]?.distance);
     if(!Number.isFinite(meters)||meters<0)throw Error("Distanza non valida");
     weeklyRouteCache.set(key,meters/1000);
    }
    distances.set(key,weeklyRouteCache.get(key));
   }catch(e){distances.set(key,null);failed.push(route.from+" → "+route.to+": "+e.message)}
  }
  for(const trip of calendar){
   if(!Number.isInteger(trip.day)||trip.day<0||trip.day>6||!regions[trip.from]||!regions[trip.to])continue;
   const km=distances.get(JSON.stringify([regions[trip.from],regions[trip.to]]));
   if(km!=null)byDay[trip.day]+=km;
  }
  const total=byDay.reduce((a,b)=>a+b,0);
  const euro=n=>n.toFixed(2).replace(".",",")+" €";
  const fmt=n=>n.toFixed(2).replace(".",",");
  const table=document.createElement("table");
  const head=document.createElement("thead");head.innerHTML="<tr><th>Giorno</th><th>🛵 km</th><th>⛽ L</th><th>💶 €</th></tr>";table.append(head);
  const tbody=document.createElement("tbody");
  byDay.forEach((km,i)=>{
   const tr=document.createElement("tr");
   for(const val of [weekdays[i],fmt(km),fmt(km*consumption/100),price?euro(km*consumption/100*price):"n.d."]){
    const td=document.createElement("td");td.textContent=val;tr.append(td);
   }
   tbody.append(tr);
  });table.append(tbody);
  const foot=document.createElement("tfoot"),tr=document.createElement("tr");
  for(const val of ["Totale settimana",fmt(total),fmt(total*consumption/100),price?euro(total*consumption/100*price):"n.d."]){
   const td=document.createElement("td");td.textContent=val;tr.append(td);
  }
  foot.append(tr);table.append(foot);
  out.replaceChildren();
  const title=document.createElement("h3");title.textContent="📊 Consumi settimanali";out.append(title);
  const scroll=document.createElement("div");scroll.className="report-scroll";scroll.append(table);out.append(scroll);
  const note=document.createElement("p");note.textContent="Consumo impostato: "+fmt(consumption)+" L/100 km. "+(price?"Prezzo benzina: "+price.toFixed(3).replace(".",",")+" €/L.":"Prezzo benzina aggiornato non disponibile: costo in euro non calcolato.");out.append(note);
  if(failed.length){
   const warning=document.createElement("p");warning.style.color="#ffb3b3";
   warning.textContent="⚠️ "+failed.length+" percorso/i non calcolati: "+failed.join("; ")+". I totali sono parziali.";
   out.append(warning);
  }
 }catch(e){out.textContent="Errore nel calcolo: "+e.message}
 finally{button.disabled=false}
});
function resetEdit(){editingTrip=null;$("calSave").textContent="Salva tragitto";$("calDialogTitle").textContent="➕ Aggiungi tragitto";$("calDialog").close()}
$("calOpen").onclick=()=>{
 editingTrip=null;renderCalendarSelectors();$("calFavorite").value="";
 $("calDay").value=(new Date().getDay()+6)%7;$("calTime").value="09:00";
 $("calDialogTitle").textContent="➕ Aggiungi tragitto";$("calSave").textContent="Salva tragitto";$("calDialog").showModal();
};
$("calCancel").onclick=resetEdit;
$("calDialog").addEventListener("close",()=>{editingTrip=null});
$("calSave").onclick=()=>{
 const trip={id:editingTrip||crypto.randomUUID(),day:Number($("calDay").value),time:$("calTime").value,from:$("calFrom").value,to:$("calTo").value};
 if(!trip.time||!regions[trip.from]||!regions[trip.to]){alert("Completa i campi del tragitto");return}
 if(editingTrip)calendar=calendar.map(t=>t.id===editingTrip?trip:t);else calendar.push(trip);
 persistCalendar();resetEdit();
};
renderCalendarSelectors();
renderCalendar();

const apiFile="https://api.github.com/repos/giacomoubaldi/meteo-scooter-bologna/contents/data/config.json";
let remoteSha=null,dirty=false,loadingRemote=false;
function queueSync(){if(!loadingRemote){dirty=true;$("syncStatus").textContent="Modifiche da salvare: premi Commit and Reload."}}
function b64Encode(value){return btoa(Array.from(new TextEncoder().encode(value),b=>String.fromCharCode(b)).join(""))}
function b64Decode(value){return new TextDecoder().decode(Uint8Array.from(atob(value.replace(/\s/g,"")),c=>c.charCodeAt(0)))}
const rawConfig="https://raw.githubusercontent.com/giacomoubaldi/meteo-scooter-bologna/main/data/config.json";
async function getConfig(token=null){
 if(!token){
  const response=await fetch(rawConfig+"?nocache="+Date.now(),{cache:"no-store"});
  if(!response.ok)throw Error("Lettura file pubblico: HTTP "+response.status);
  return {sha:null,data:await response.json()};
 }
 const response=await fetch(apiFile,{headers:{"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json"},cache:"no-store"});
 if(!response.ok)throw Error("Lettura autenticata GitHub: HTTP "+response.status);
 const file=await response.json();
 return {sha:file.sha,data:JSON.parse(b64Decode(file.content))};
}
function applyConfig(data){
 loadingRemote=true;
 regions={...defaults,...(data.tappe||{})};
 favorites=Array.isArray(data.favorites)?data.favorites:[];
 calendar=Array.isArray(data.calendar)?data.calendar:[];
 localStorage.setItem("regionsScooter",JSON.stringify(regions));
 localStorage.setItem(favoritesKey,JSON.stringify(favorites));
 localStorage.setItem(calKey,JSON.stringify(calendar));
 render();renderFavorites();renderCalendarSelectors();renderCalendar();
 loadingRemote=false;dirty=false;
}
async function loadConfig(){
 try{const {sha,data}=await getConfig();remoteSha=sha;applyConfig(data);$("syncStatus").textContent="Dati caricati da GitHub."}
 catch(e){$("syncStatus").textContent="Caricamento non riuscito: "+e.message}
}
$("commitReload").onclick=()=>{$("tokenError").textContent="";$("tokenDialog").showModal();$("githubToken").focus()};
$("tokenCancel").onclick=()=>{$("tokenDialog").close();$("githubToken").value=""};
$("tokenForm").addEventListener("submit",async event=>{
 event.preventDefault();
 const token=$("githubToken").value.trim();
 if(!token)return;
 const button=$("tokenSubmit");button.disabled=true;
 $("tokenError").textContent="";
 try{
  const latest=await getConfig(token);
  if(remoteSha&&latest.sha!==remoteSha)throw Error("I dati sono cambiati su un altro dispositivo. Ricarica prima di salvare.");
  const payload={tappe:regions,favorites,calendar};
  const r=await fetch(apiFile,{method:"PUT",headers:{"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json","Content-Type":"application/json"},body:JSON.stringify({message:"Update scooter calendar, stops and favorites",content:b64Encode(JSON.stringify(payload,null,2)),sha:latest.sha,branch:"main"})});
  if(!r.ok)throw Error("Commit non riuscito: HTTP "+r.status);
  $("syncStatus").textContent="Commit completato. Ricaricamento…";
  $("tokenDialog").close();
  $("githubToken").value="";
  location.reload();
 }catch(e){$("tokenError").textContent=e.message}
 finally{button.disabled=false}
});

loadConfig();
