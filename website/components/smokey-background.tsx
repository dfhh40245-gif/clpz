"use client";

import { useEffect, useRef } from "react";

const vertexSource = `attribute vec4 a_position;void main(){gl_Position=a_position;}`;
const fragmentSource = `precision mediump float;
uniform vec2 iResolution;uniform float iTime;uniform vec2 iMouse;uniform vec3 u_color;
void mainImage(out vec4 fragColor,in vec2 fragCoord){
vec2 centeredUV=(2.0*fragCoord-iResolution.xy)/min(iResolution.x,iResolution.y);
float time=iTime*0.5;vec2 mouse=iMouse/iResolution;vec2 rippleCenter=2.0*mouse-1.0;vec2 distortion=centeredUV;
for(float i=1.0;i<8.0;i++){distortion.x+=0.5/i*cos(i*2.0*distortion.y+time+rippleCenter.x*3.1415);distortion.y+=0.5/i*cos(i*2.0*distortion.x+time+rippleCenter.y*3.1415);}
float wave=abs(sin(distortion.x+distortion.y+time));float glow=smoothstep(0.9,0.2,wave);fragColor=vec4(u_color*glow,1.0);}
void main(){mainImage(gl_FragColor,gl_FragCoord.xy);}`;

export function SmokeyBackground({ className = "" }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouseRef = useRef({ x: 0, y: 0, active: false });

  useEffect(() => {
    const canvas = canvasRef.current;
    const gl = canvas?.getContext("webgl");
    if (!canvas || !gl) return;
    const compile = (type: number, source: string) => { const shader=gl.createShader(type); if(!shader)return null; gl.shaderSource(shader,source); gl.compileShader(shader); if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS)){gl.deleteShader(shader);return null;} return shader; };
    const vertex=compile(gl.VERTEX_SHADER,vertexSource), fragment=compile(gl.FRAGMENT_SHADER,fragmentSource);
    if(!vertex||!fragment)return;
    const program=gl.createProgram(); if(!program)return;
    gl.attachShader(program,vertex);gl.attachShader(program,fragment);gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))return;gl.useProgram(program);
    const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]),gl.STATIC_DRAW);
    const position=gl.getAttribLocation(program,"a_position");gl.enableVertexAttribArray(position);gl.vertexAttribPointer(position,2,gl.FLOAT,false,0,0);
    const resolution=gl.getUniformLocation(program,"iResolution"), time=gl.getUniformLocation(program,"iTime"), mouse=gl.getUniformLocation(program,"iMouse"), color=gl.getUniformLocation(program,"u_color");
    gl.uniform3f(color,240/255,160/255,48/255);
    const trackPointer=(event:PointerEvent)=>{const rect=canvas.getBoundingClientRect();mouseRef.current={x:event.clientX-rect.left,y:event.clientY-rect.top,active:true};};
    const clearPointer=()=>{mouseRef.current.active=false;};
    window.addEventListener("pointermove",trackPointer,{passive:true});window.addEventListener("pointerleave",clearPointer);
    const start=performance.now();let frame=0,last=0;
    const render=(now:number)=>{frame=requestAnimationFrame(render);if(now-last<33)return;last=now;const ratio=Math.min(devicePixelRatio||1,1),width=Math.round(canvas.clientWidth*ratio),height=Math.round(canvas.clientHeight*ratio);if(canvas.width!==width||canvas.height!==height){canvas.width=width;canvas.height=height;}gl.viewport(0,0,width,height);gl.uniform2f(resolution,width,height);gl.uniform1f(time,(now-start)/1000);const m=mouseRef.current;gl.uniform2f(mouse,m.active?m.x*ratio:width/2,m.active?height-m.y*ratio:height/2);gl.drawArrays(gl.TRIANGLES,0,6);};
    frame=requestAnimationFrame(render);return()=>{cancelAnimationFrame(frame);window.removeEventListener("pointermove",trackPointer);window.removeEventListener("pointerleave",clearPointer);gl.deleteProgram(program);gl.deleteShader(vertex);gl.deleteShader(fragment);};
  }, []);

  return <div className={`smokey-background ${className}`} aria-hidden="true"><canvas ref={canvasRef} /></div>;
}
