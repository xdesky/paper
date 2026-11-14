import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import type {Spec} from './types';
const palette = ['#c6ded6','#edd9ba','#d3d9ea','#e4cdd8','#dce8c4','#c5dce9'];
export function ModelViewer({spec,seam,wire}:{spec:Spec;seam:string;wire:boolean}) {
  const host = useRef<HTMLDivElement>(null);
  const [error,setError] = useState('');
  useEffect(()=>{
    const target=host.current!; let renderer:THREE.WebGLRenderer;
    try { renderer=new THREE.WebGLRenderer({antialias:true,alpha:true}); } catch {setError('WebGL không khả dụng. Xem ảnh 3D trong mục Xuất file.');return;}
    setError(''); renderer.setPixelRatio(Math.min(devicePixelRatio,2)); target.appendChild(renderer.domElement);
    const scene=new THREE.Scene(); const group=new THREE.Group(); scene.add(group);
    const camera=new THREE.PerspectiveCamera(35,1,0.1,10000);
    const convert=(p:number[])=>new THREE.Vector3(p[0],p[2],-p[1]);
    const selected=spec.geometry.seams.find(s=>s.id===seam);
    const textures:THREE.Texture[]=[];
    spec.geometry.panels.forEach((panel,i)=>{
      const points=panel.vertices_3d_mm.map(convert);
      const geometry=new THREE.BufferGeometry().setFromPoints(points);
      const indices:number[]=[];for(let n=1;n<points.length-1;n++)indices.push(0,n,n+1);
      geometry.setIndex(indices);geometry.computeVertexNormals();
      let texture:THREE.Texture|undefined;
      const art=spec.appearance?.panels[panel.id];
      if(art&&panel.polygon_mm){
        geometry.setAttribute('uv',new THREE.Float32BufferAttribute(panel.polygon_mm.flatMap(p=>[p[0]/panel.width_mm!,p[1]/panel.height_mm!]),2));
        texture=new THREE.TextureLoader().load('data:image/svg+xml;charset=utf-8,'+encodeURIComponent(art));texture.colorSpace=THREE.SRGBColorSpace;textures.push(texture);
      }
      const face=new THREE.Mesh(geometry,new THREE.MeshStandardMaterial({color:texture?'#ffffff':palette[i%6],map:texture,side:THREE.DoubleSide,roughness:.8,wireframe:wire})); group.add(face);
      const edge=new THREE.LineSegments(new THREE.EdgesGeometry(geometry),new THREE.LineBasicMaterial({color:'#527168'}));group.add(edge);
      const mate=selected?.mates.find(m=>m.panel===panel.id);
      if(mate){const n={S:0,E:1,N:2,W:3}[mate.edge]??Number(mate.edge);const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints([points[n],points[(n+1)%points.length]]),new THREE.LineBasicMaterial({color:'#ec5b32',depthTest:false}));line.renderOrder=10;group.add(line);}
    });
    const bounds=new THREE.Box3().setFromObject(group), center=bounds.getCenter(new THREE.Vector3()), size=bounds.getSize(new THREE.Vector3());
    group.position.sub(center); const extent=Math.max(size.x,size.y,size.z);
    camera.position.set(extent*1.9,extent*1.4,extent*2.3);
    scene.add(new THREE.HemisphereLight(0xffffff,0xa7b5ad,2.6)); const light=new THREE.DirectionalLight(0xffffff,2);light.position.set(300,500,400);scene.add(light);
    const grid=new THREE.GridHelper(extent*2.5,10,0xb3c8c0,0xd6e2db);grid.position.y=-size.y/2-.5;scene.add(grid);
    const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.minDistance=extent*.5;controls.maxDistance=extent*8;
    const resize=new ResizeObserver(()=>{const w=target.clientWidth,h=target.clientHeight;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();});resize.observe(target);
    let raf=0;const frame=()=>{controls.update();renderer.render(scene,camera);raf=requestAnimationFrame(frame);};frame();
    return()=>{cancelAnimationFrame(raf);resize.disconnect();controls.dispose();textures.forEach(t=>t.dispose());scene.traverse(o=>{if(o instanceof THREE.Mesh||o instanceof THREE.Line){o.geometry.dispose();(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>m.dispose());}});renderer.dispose();target.replaceChildren();};
  },[spec,seam,wire]);
  return <div className="model-view" ref={host} aria-label="Mô hình 3D xoay, zoom và pan">{error&&<p role="alert">{error}</p>}</div>;
}
