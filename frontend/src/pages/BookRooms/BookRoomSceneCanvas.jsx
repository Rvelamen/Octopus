import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { ArcRotateCamera } from '@babylonjs/core/Cameras/arcRotateCamera';
import '@babylonjs/core/Cameras/Inputs/arcRotateCameraPointersInput';
import '@babylonjs/core/Cameras/Inputs/arcRotateCameraMouseWheelInput';
import { Engine } from '@babylonjs/core/Engines/engine';
import { Scene } from '@babylonjs/core/scene';
import { Vector3, Matrix } from '@babylonjs/core/Maths/math.vector';
import { Color3, Color4 } from '@babylonjs/core/Maths/math.color';
import { HemisphericLight } from '@babylonjs/core/Lights/hemisphericLight';
import { DirectionalLight } from '@babylonjs/core/Lights/directionalLight';
import { StandardMaterial } from '@babylonjs/core/Materials/standardMaterial';
import { TransformNode } from '@babylonjs/core/Meshes/transformNode';
import { CreateCylinder } from '@babylonjs/core/Meshes/Builders/cylinderBuilder';
import { PointerEventTypes } from '@babylonjs/core/Events/pointerEvents';
import '@babylonjs/core/Culling/ray';
import { BOOK_COLORS, WOOD, sceneBox, sceneSphere } from '../Knowledge/library/scene/scenePrimitives';
import { seatPosition } from './sceneProjection.mjs';

const diagnostics = { created: 0, disposed: 0, active: 0, meshes: 0, fps: 0 };
export const getBookSceneDiagnostics = () => ({ ...diagnostics });

class RoundTableRenderer {
  constructor(canvas, projection, callbacks) {
    this.canvas = canvas; this.callbacks = callbacks; this.materials = new Map(); this.seats = new Map();
    try {
      this.engine = new Engine(canvas, true, { stencil: false, powerPreference: 'high-performance' });
      this.engine.setHardwareScalingLevel(1 / Math.min(window.devicePixelRatio || 1, 1.5));
      this.scene = new Scene(this.engine); this.scene.clearColor = Color4.FromHexString('#e8eee1ff');
      this.camera = new ArcRotateCamera('room-camera', -Math.PI / 2, .86, 11, new Vector3(0, .8, 0), this.scene);
      this.camera.lowerBetaLimit = .2; this.camera.upperBetaLimit = 1.48;
      this.camera.lowerRadiusLimit = 3; this.camera.upperRadiusLimit = 50;
      this.camera.wheelPrecision = 25; this.camera.attachControl(canvas, true);
      new HemisphericLight('room-daylight', new Vector3(0,1,0), this.scene).intensity = .9;
      const sunlight = new DirectionalLight('warm-sun', new Vector3(-1,-2,1), this.scene);
      sunlight.diffuse = Color3.FromHexString('#ffe5bf'); sunlight.intensity = .45;
      this.build(projection.capacity);
      this.update(projection);
      this.scene.onPointerObservable.add(event => {
        if (event.type === PointerEventTypes.POINTERPICK) {
          let node = event.pickInfo?.pickedMesh;
          while (node && !node.metadata?.member_id) node = node.parent;
          if (node?.metadata?.member_id) callbacks.onSelect(node.metadata.member_id);
        }
      });
      this.resize = new ResizeObserver(() => this.engine.resize()); this.resize.observe(canvas);
      this.lost = event => { event.preventDefault(); callbacks.onError('WebGL context lost'); };
      canvas.addEventListener('webglcontextlost', this.lost);
      this.engine.runRenderLoop(() => {
        if (document.hidden || this.disposed) return;
        this.scene.render();
        this.project();
        diagnostics.fps = this.engine.getFps(); diagnostics.meshes = this.scene.meshes.length;
      });
      diagnostics.created += 1; diagnostics.active += 1; this.counted = true;
    } catch (error) { this.dispose(); throw error; }
  }
  material(color) {
    if (!this.materials.has(color)) {
      const material = new StandardMaterial(color, this.scene);
      material.diffuseColor = Color3.FromHexString(color); material.specularColor = Color3.Black();
      this.materials.set(color, material);
    }
    return this.materials.get(color);
  }
  box(name, dimensions, position, color, parent) { return sceneBox(this.scene, color => this.material(color), name, dimensions, position, color, parent); }
  sphere(name, diameter, position, color, parent, scale) { return sceneSphere(this.scene, color => this.material(color), name, diameter, position, color, parent, scale); }
  cylinder(name, diameter, height, position, color, parent = null) {
    const mesh = CreateCylinder(name, { diameter, height, tessellation: 24 }, this.scene);
    mesh.position = new Vector3(...position); mesh.material = this.material(color); mesh.parent = parent;
    return mesh;
  }
  build(capacity) {
    this.capacity = capacity;
    const radius = seatPosition(0, capacity).radius;
    this.cylinder('forest-floor', radius*2+5,.15,[0,-.09,0],'#cbd7bc');
    this.cylinder('wood-table', (radius-.7)*2,.18,[0,.96,0],WOOD.oak);
    this.cylinder('table-pedestal', .5,.92,[0,.46,0],WOOD.walnut);
    this.cylinder('table-foot', 1.3,.08,[0,.06,0],WOOD.ebony);
    this.box('open-book', {width:.5,height:.06,depth:.35},[0,1.08,0],'#fff1d5');
    for (let index=0;index<capacity;index+=1) {
      const location = seatPosition(index, capacity);
      const root = new TransformNode(`seat-${index}`,this.scene);
      root.position = new Vector3(location.x,0,location.z); root.rotation.y = Math.atan2(-location.x,-location.z);
      this.box('chair-frame',{width:.6,height:.1,depth:.6},[0,.42,0],WOOD.walnut,root);
      this.cylinder('chair-cushion',.66,.13,[0,.53,0],BOOK_COLORS[index%BOOK_COLORS.length],root);
      this.sphere('chair-back',.65,[0,.86,-.3],'#9bb8a0',root,[1,1,.22]);
      for (const x of [-.22,.22]) for (const z of [-.22,.22]) this.box('chair-leg',{width:.08,height:.43,depth:.08},[x,.2,z],WOOD.walnut,root);
      const person = new TransformNode(`person-${index}`,this.scene); person.parent=root;
      const clothing = BOOK_COLORS[index%BOOK_COLORS.length];
      this.sphere('torso',.57,[0,1.02,.02],clothing,person,[.85,1.2,.6]);
      this.sphere('head',.27,[0,1.49,.02],'#c2b294',person,[1,1.12,1]);
      for(const x of [-.15,.15]) {
        this.box('seated-thigh',{width:.18,height:.18,depth:.46},[x,.69,.2],clothing,person);
        this.box('seated-shin',{width:.14,height:.5,depth:.15},[x,.4,.41],clothing,person);
        this.box('shoe',{width:.18,height:.1,depth:.27},[x,.12,.46],WOOD.ebony,person);
        const arm=this.box('resting-arm',{width:.1,height:.42,depth:.13},[x*1.6,.89,.1],clothing,person);arm.rotation.x=-.5;
      }
      person.setEnabled(false); this.seats.set(index,{root,person,head:new Vector3(location.x,1.78,location.z)});
    }
    for(let index=0;index<8;index+=1) {
      const angle=index*Math.PI/4, x=Math.cos(angle)*(radius+3.5),z=Math.sin(angle)*(radius+3.5);
      this.cylinder('tree-trunk',.18,2.3,[x,1.1,z],WOOD.walnut);
      this.sphere('forest-canopy',1.1,[x,2.6,z], index%2 ? '#9caf8c' : '#7f9e82', null,[1,.7,1]);
    }
    this.reset();
  }
  update(projection) {
    this.projection = projection;
    for(const seat of this.seats.values()) { seat.root.metadata=null; seat.person.setEnabled(false); }
    for(const member of projection.members) {
      const seat=this.seats.get(member.seat_index);
      if(seat) { seat.root.metadata={member_id:member.member_id}; seat.person.setEnabled(member.present); }
    }
  }
  project() {
    const width=this.canvas.clientWidth,height=this.canvas.clientHeight;
    const viewport=this.camera.viewport.toGlobal(width,height);
    const positions=this.projection.members.map(member=>{
      const head=this.seats.get(member.seat_index)?.head;
      const point=head&&Vector3.Project(head,Matrix.Identity(),this.scene.getTransformMatrix(),viewport);
      return {id:member.member_id,x:point?.x||0,y:point?.y||0,visible:Boolean(point&&point.z>=0&&point.z<1&&point.x>0&&point.x<width&&point.y>0&&point.y<height)};
    });
    const key=positions.map(point=>`${point.id}:${Math.round(point.x)}:${Math.round(point.y)}:${point.visible}`).join('|');
    if(key!==this.projectedKey) {this.projectedKey=key;this.callbacks.onProject(positions);}
  }
  reset() { this.camera.setTarget(new Vector3(0,.8,0));this.camera.radius=seatPosition(0,this.capacity).radius*3.7;this.camera.alpha=-Math.PI/2;this.camera.beta=.86; }
  focus(memberId) { const member=this.projection.members.find(member=>member.member_id===memberId);const seat=member&&this.seats.get(member.seat_index);if(seat)this.camera.setTarget(seat.head); }
  zoom(direction) {this.camera.radius=Math.max(3,Math.min(50,this.camera.radius*direction));}
  dispose() {
    if(this.disposed)return;this.disposed=true;
    this.resize?.disconnect();if(this.lost)this.canvas.removeEventListener('webglcontextlost',this.lost);
    this.engine?.stopRenderLoop();this.scene?.dispose();this.engine?.dispose();
    if(this.counted){diagnostics.disposed+=1;diagnostics.active-=1;}
  }
}

const BookRoomSceneCanvas=forwardRef(function BookRoomSceneCanvas({projection,onSelect,onError,children},ref){
  const canvas=useRef(null),renderer=useRef(null),callbacks=useRef({onSelect,onError});
  const [positions,setPositions]=useState([]);callbacks.current={onSelect,onError};
  useImperativeHandle(ref,()=>({reset:()=>renderer.current?.reset(),focus:id=>renderer.current?.focus(id),zoom:value=>renderer.current?.zoom(value)}),[]);
  const key=`${projection.room_id}:${projection.layout_version}:${projection.capacity}`;
  const initial=useRef(projection);initial.current=projection;
  useEffect(()=>{
    let instance;
    try{instance=new RoundTableRenderer(canvas.current,initial.current,{onSelect:id=>callbacks.current.onSelect(id),onError:error=>callbacks.current.onError(error),onProject:setPositions});renderer.current=instance;}
    catch(error){callbacks.current.onError(error.message);}
    return()=>{renderer.current=null;instance?.dispose();};
  },[key]);
  useEffect(()=>{renderer.current?.update(projection);},[projection]);
  return <div className="book-room-canvas"><canvas ref={canvas} aria-label="3D round table; use the member list for keyboard controls"/>{children(positions)}</div>;
});
export default BookRoomSceneCanvas;
