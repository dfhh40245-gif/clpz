package com.clpz.mobile

import android.content.Context
import android.net.Uri
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

data class ClipProject(val id:String=UUID.randomUUID().toString(),val name:String,val sourceUri:String,val sourceDurationMs:Long,val startMs:Long,val endMs:Long,val caption:String="",val aspect:String="9:16",val updatedAt:Long=System.currentTimeMillis())

class ProjectStore(context: Context) {
    private val prefs=context.getSharedPreferences("clpz_projects",Context.MODE_PRIVATE)
    fun load():List<ClipProject>{val rows=JSONArray(prefs.getString("rows","[]"));return (0 until rows.length()).mapNotNull{i->runCatching{val o=rows.getJSONObject(i);val end=o.getLong("endMs");ClipProject(o.getString("id"),o.getString("name"),o.getString("sourceUri"),o.optLong("sourceDurationMs",end),o.getLong("startMs"),end,o.optString("caption"),o.optString("aspect","9:16"),o.optLong("updatedAt"))}.getOrNull()}.sortedByDescending{it.updatedAt}}
    fun save(project:ClipProject){val all=load().filterNot{it.id==project.id}.toMutableList();all.add(project.copy(updatedAt=System.currentTimeMillis()));write(all)}
    fun remove(id:String)=write(load().filterNot{it.id==id})
    private fun write(rows:List<ClipProject>){val json=JSONArray();rows.forEach{p->json.put(JSONObject().apply{put("id",p.id);put("name",p.name);put("sourceUri",p.sourceUri);put("sourceDurationMs",p.sourceDurationMs);put("startMs",p.startMs);put("endMs",p.endMs);put("caption",p.caption);put("aspect",p.aspect);put("updatedAt",p.updatedAt)})};prefs.edit().putString("rows",json.toString()).apply()}
    fun suggestions(uri: Uri,durationMs:Long):List<ClipProject>{val safeDuration=durationMs.coerceAtLeast(1_000L);val length=minOf(45_000L,safeDuration);val starts=listOf(0L,(safeDuration/2-length/2).coerceAtLeast(0),(safeDuration-length).coerceAtLeast(0)).distinct();return starts.mapIndexed{i,start->ClipProject(name="Moment ${i+1}",sourceUri=uri.toString(),sourceDurationMs=safeDuration,startMs=start,endMs=(start+length).coerceAtMost(safeDuration))}}
}
