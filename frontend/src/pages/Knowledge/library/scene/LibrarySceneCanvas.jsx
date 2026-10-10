import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import { ArcRotateCamera } from '@babylonjs/core/Cameras/arcRotateCamera';
import { ArcRotateCameraPointersInput } from '@babylonjs/core/Cameras/Inputs/arcRotateCameraPointersInput';
import { ArcRotateCameraMouseWheelInput } from '@babylonjs/core/Cameras/Inputs/arcRotateCameraMouseWheelInput';
import { Color3, Color4 } from '@babylonjs/core/Maths/math.color';
import { Vector3 } from '@babylonjs/core/Maths/math.vector';
import { Engine } from '@babylonjs/core/Engines/engine';
import { Scene } from '@babylonjs/core/scene';
import { DirectionalLight } from '@babylonjs/core/Lights/directionalLight';
import { HemisphericLight } from '@babylonjs/core/Lights/hemisphericLight';
import { ShadowGenerator } from '@babylonjs/core/Lights/Shadows/shadowGenerator';
import '@babylonjs/core/Lights/Shadows/shadowGeneratorSceneComponent';
import { PointLight } from '@babylonjs/core/Lights/pointLight';
import '@babylonjs/core/Lights/Shadows/shadowGeneratorSceneComponent';
import { StandardMaterial } from '@babylonjs/core/Materials/standardMaterial';
import { DynamicTexture } from '@babylonjs/core/Materials/Textures/dynamicTexture';
import { PointerDragBehavior } from '@babylonjs/core/Behaviors/Meshes/pointerDragBehavior';
import { PointerEventTypes } from '@babylonjs/core/Events/pointerEvents';
import '@babylonjs/core/Culling/ray';
import { CreateBox } from '@babylonjs/core/Meshes/Builders/boxBuilder';
import { CreateSphere } from '@babylonjs/core/Meshes/Builders/sphereBuilder';
import { CreatePlane } from '@babylonjs/core/Meshes/Builders/planeBuilder';
import { CreateCylinder } from '@babylonjs/core/Meshes/Builders/cylinderBuilder';
import { CreateTorus } from '@babylonjs/core/Meshes/Builders/torusBuilder';

const MeshBuilder = { CreateBox, CreateSphere, CreatePlane, CreateCylinder, CreateTorus };

// 通用色板 — 暖石灰岩 / 木材 / 织物
const STONE = { light: '#c2b294', mid: '#a89a82', dark: '#7e7058', shadow: '#5d5240' };
const WOOD = { oak: '#caa17a', walnut: '#9c6f44', cherry: '#bd8a5e', ebony: '#5d4126' };
const BOOK_COLORS = ['#c27e69', '#7e9e92', '#8ca9be', '#d0b477', '#af92af', '#708e9b', '#c9947d', '#8a8265', '#b08a6e'];

// The renderer owns GPU resources; application state and book data stay in React.
class LibraryRenderer {
  constructor(canvas, callbacks) {
    this.canvas = canvas;
    this.callbacks = callbacks;
    this.materials = new Map();
    this.regions = new Map();
    this.thinker = null;
    this.editing = false;
    this.activeId = null;
    this.hovered = null;
    this.engine = new Engine(canvas, true, {
      stencil: false, // 不需要模板缓冲:省一笔固定开销
      antialias: true,
      powerPreference: 'high-performance',
      adaptToDeviceRatio: true,
    });
    // 渲染分辨率:高分屏封顶 1.5x(原本 2x 等于 4 倍像素,4K 屏幕 GPU 直接爆),
    // 普通屏 1.0x 即可。tradeoff 文字/书脊稍糊,但拖动流畅度提升明显。
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    this.engine.setHardwareScalingLevel(1 / dpr);
    this.scene = new Scene(this.engine);
    this.scene.clearColor = Color4.FromHexString('#e7efdfFF');
    this.scene.autoClear = true;
    this.scene.autoClearDepthAndStencil = true;
    // 不开 constantlyUpdateMeshUnderPointer:它会每帧做一次 raycast,几何多时是性能大头。
    // Babylon 在 pointerdown/move/up 时会主动做 pick,够用。
    this.scene.constantlyUpdateMeshUnderPointer = false;
    this.scene.skipPointerMovePicking = true; // 普通移动不 pick,只响应带 hit 的对象
    this.scene.blockMaterialDirtyMechanism = true; // 材质参数不再每帧重算
    // 色调映射本身是一遍 post-processing pass,关掉换更便宜的固定颜色叠加;
    // 视觉差异极小,但每帧省下 fragment shader 一遍。
    this.scene.imageProcessingConfiguration.toneMappingEnabled = false;
    this.scene.imageProcessingConfiguration.exposure = 1.0;
    this.scene.imageProcessingConfiguration.contrast = 1.0;
    this.camera = new ArcRotateCamera('library-camera', -Math.PI / 2 - 0.25, 0.9, 22, new Vector3(0, 0.8, 0), this.scene);
    this.camera.minZ = 0.1;
    this.camera.maxZ = 180;
    this.camera.lowerRadiusLimit = 3.5;
    this.camera.upperRadiusLimit = 60;
    this.camera.lowerBetaLimit = 0.15;
    this.camera.upperBetaLimit = Math.PI / 2 - 0.05;
    this.camera.angularSensibilityX = 800;
    this.camera.angularSensibilityY = 800;
    this.camera.inertia = 0.7;
    // 默认「拖动 = 旋转」;用户可以切到 panMode,变成「拖动 = 平移」
    // (适配用户说的"鼠标拖拽页面滚动,这样可以看任意地方的物体")
    this.panMode = false;
    // 重新挂回指针(拖动旋转 / 平移) + 滚轮(缩放) — 默认 clear() 把它们清掉了
    this.camera.inputs.clear();
    // ArcRotateCameraPointersInput 默认 button=2(右键)=pan,button=0/1(左/中)=rotate
    this.pointersInput = new ArcRotateCameraPointersInput();
    this.wheelInput = new ArcRotateCameraMouseWheelInput();
    this.camera.inputs.add(this.pointersInput);
    this.camera.inputs.add(this.wheelInput);
    // 关键:Babylon 的滚轮/平移灵敏度是「输入」自己的字段,不是 camera 上的 —
    // 之前写在 camera.wheelPrecision / camera.panningSensibility 实际上被 input 默认值覆盖了。
    // 这里直接改 input,让平移和滚轮都按新值生效。
    this.wheelInput.wheelPrecision = 4; // 数字越小越灵敏(默认 3)
    this.pointersInput.panningSensibility = 600; // 数字越小越灵敏(默认 1000)
    // inputs.clear() 会从 canvas 上摘掉旧 input;新加的 input 默认不会自动 attach,
    // 必须再调一次 attachControl,让新 input 重新绑到 canvas 事件上 ——
    // 否则滚轮和拖动事件根本不会到达相机,这就是之前"什么都不响应"的根因。
    this.camera.attachControl(this.canvas, true);
    // 屏蔽浏览器/Electron 的右键菜单,让右拖平移能正常触发
    this._suppressContextMenu = (event) => event.preventDefault();
    this.canvas.addEventListener('contextmenu', this._suppressContextMenu);
    this.scene.activeCamera = this.camera;
    new HemisphericLight('soft-daylight', new Vector3(0, 1, 0), this.scene).intensity = 0.75;
    const sun = new DirectionalLight('afternoon-sun', new Vector3(-0.5, -1, 0.4), this.scene);
    sun.position = new Vector3(8, 16, -10);
    sun.intensity = 0.4;
    sun.diffuse = Color3.FromHexString('#fff0d5');
    this.shadows = new ShadowGenerator(512, sun);
    this.shadows.useBlurExponentialShadowMap = false; // 模糊 ESM 较贵,改用普通 ESM 已经够柔和
    this.shadows.usePoissonSampling = true; // PCF 软阴影,比 blur ESM 便宜
    this.shadows.darkness = 0.55;
    this.environment = [];
    this.overview = { target: new Vector3(0, 0.8, 0), radius: 22, alpha: -Math.PI / 2 - 0.25, beta: 0.9 };
    this.destination = { ...this.overview, target: this.overview.target.clone() };
    this.reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    this.userInteracting = false;
    this.scene.onPointerObservable.add((info) => this.onPointer(info));
    this._lerpEps = 0.0005; // 视为"已到达 destination"的阈值
    this.renderFrame = () => {
      const dt = this.engine.getDeltaTime();
      // 自适应 easing:长时间空闲后让补间更利落,避免长尾的"慢拖"
      const easing = this.reducedMotion ? 1 : 1 - Math.exp(-dt / 110);
      // 头几帧强制 render(setAreas 之后):保证新场景先被画出来,再进入跳帧模式
      if (this._framesToForce > 0) this._framesToForce -= 1;
      let atRest = !this.userInteracting && this._framesToForce === 0 && !this.hovered;
      if (!this.userInteracting) {
        // 关键优化:不再用 Vector3.Lerp —— 它每帧都 new 一个 Vector3,
        // 60fps 下来每秒 60 个临时对象,GC 抖动会直接表现为拖动卡顿。
        // 改成直接改 x/y/z,零分配。
        const cur = this.camera.target;
        const dst = this.destination.target;
        const dx = (dst.x - cur.x) * easing;
        const dy = (dst.y - cur.y) * easing;
        const dz = (dst.z - cur.z) * easing;
        cur.x += dx; cur.y += dy; cur.z += dz;
        if (Math.abs(dx) > this._lerpEps || Math.abs(dy) > this._lerpEps || Math.abs(dz) > this._lerpEps) atRest = false;
        const dr = (this.destination.radius - this.camera.radius) * easing;
        const da = (this.destination.alpha - this.camera.alpha) * easing;
        const db = (this.destination.beta - this.camera.beta) * easing;
        this.camera.radius += dr;
        this.camera.alpha += da;
        this.camera.beta += db;
        if (Math.abs(dr) > this._lerpEps || Math.abs(da) > this._lerpEps || Math.abs(db) > this._lerpEps) atRest = false;
      } else {
        atRest = false;
      }
      if (this.hovered) {
        // 悬停书本的「浮起」动画,只改一个 z 字段,无分配
        this.hovered.position.z += (-0.14 - this.hovered.position.z) * easing;
        atRest = false;
      }
      // 真正「静止」时跳过场景渲染 —— 静态画面反复重画对 CPU/GPU 都是浪费。
      if (!atRest) this.scene.render();
    };
    this.engine.runRenderLoop(this.renderFrame);
    // 跟踪用户是否正在与相机交互
    let wheelTimeout = null;
    const markInteract = () => { this.userInteracting = true; };
    // 释放时:把当前 camera 的所有角度都同步到 destination —— 不然下一帧的 lerp
    // 会把用户滚轮/旋转后到达的新位置拉回旧目标,出现「缩放完又弹回去」的卡顿感。
    const releaseInteract = () => {
      this.userInteracting = false;
      this.destination.target.copyFrom(this.camera.target);
      this.destination.radius = this.camera.radius;
      this.destination.alpha = this.camera.alpha;
      this.destination.beta = this.camera.beta;
    };
    // Shift 修饰键:按住 Shift 时,左键由「旋转」切到「平移」(更符合"鼠标拖拽页面滚动"的直觉)
    const onKeyDown = (event) => {
      if (event.key === 'Shift' && !event.repeat) {
        // 左键→平移(panningMouseButton=0),旋转灵敏度设为 0 即停转
        this.pointersInput.panningMouseButton = 0;
        this.camera.angularSensibilityX = 0;
        this.camera.angularSensibilityY = 0;
      }
    };
    const onKeyUp = (event) => {
      if (event.key === 'Shift') {
        // 恢复:右键→平移(默认 button=2),左键→旋转
        this.pointersInput.panningMouseButton = 2;
        this.camera.angularSensibilityX = 800;
        this.camera.angularSensibilityY = 800;
      }
    };
    // 滚轮节流:每次滚轮都标记「正在交互」并把 release 计时器推后 220ms,
    // 真正改变 radius 的是 Babylon 自带的 wheel input(它独立监听 canvas.wheel);
    // 我们只是需要确保:用户一直滚的时候 lerp 不会「抢」用户的位置。
    const onWheel = () => {
      markInteract();
      if (wheelTimeout) clearTimeout(wheelTimeout);
      wheelTimeout = setTimeout(() => { releaseInteract(); wheelTimeout = null; }, 220);
    };
    this.canvas.addEventListener('pointerdown', markInteract);
    this.canvas.addEventListener('pointerup', releaseInteract);
    this.canvas.addEventListener('pointercancel', releaseInteract);
    this.canvas.addEventListener('pointerleave', releaseInteract);
    this.canvas.addEventListener('wheel', onWheel, { passive: true });
    window.addEventListener('keydown', onKeyDown);
    window.addEventListener('keyup', onKeyUp);
    this._teardownCameraListeners = () => {
      this.canvas.removeEventListener('pointerdown', markInteract);
      this.canvas.removeEventListener('pointerup', releaseInteract);
      this.canvas.removeEventListener('pointercancel', releaseInteract);
      this.canvas.removeEventListener('pointerleave', releaseInteract);
      this.canvas.removeEventListener('wheel', onWheel);
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('keyup', onKeyUp);
      if (wheelTimeout) { clearTimeout(wheelTimeout); wheelTimeout = null; }
    };
    this.resizeObserver = new ResizeObserver(() => {
      this.engine.resize();
      // resize 后画布尺寸变了,旧 framebuffer 不对 —— 强制画两帧再回跳帧模式
      this._framesToForce = 2;
    });
    this.resizeObserver.observe(canvas);
    this.visibilityHandler = () => this.setRunning(document.visibilityState === 'visible');
    document.addEventListener('visibilitychange', this.visibilityHandler);
    this.intersectionObserver = new IntersectionObserver(([entry]) => this.setRunning(entry.isIntersecting && !document.hidden));
    this.intersectionObserver.observe(canvas);
  }

  material(color) {
    if (!this.materials.has(color)) {
      const material = new StandardMaterial(`material-${color}`, this.scene);
      material.diffuseColor = Color3.FromHexString(color);
      material.specularColor = Color3.Black();
      this.materials.set(color, material);
    }
    return this.materials.get(color);
  }

  box(name, dimensions, position, color, parent = null, shadow = true) {
    const mesh = MeshBuilder.CreateBox(name, dimensions, this.scene);
    mesh.position = new Vector3(...position);
    mesh.material = this.material(color);
    mesh.parent = parent;
    mesh.receiveShadows = true;
    if (shadow) this.shadows.addShadowCaster(mesh);
    return mesh;
  }

  sphere(name, diameter, position, color, parent = null, scale = [1, 1, 1]) {
    const mesh = MeshBuilder.CreateSphere(name, { diameter, segments: 8 }, this.scene);
    mesh.position = new Vector3(...position);
    mesh.scaling = new Vector3(...scale);
    mesh.material = this.material(color);
    mesh.parent = parent;
    this.shadows.addShadowCaster(mesh);
    return mesh;
  }

  label(text, parent, position, width, height, owned, background = '#f7edd7', foreground = '#655343', mirror = false) {
    const texture = new DynamicTexture(`label-${text}-${mirror ? 'm' : 'n'}`, { width: 512, height: 192 }, this.scene, false);
    const context = texture.getContext();
    if (mirror) {
      // 父节点被 180° 翻转时,贴图也要水平翻转,文字才能正向阅读
      context.translate(512, 0);
      context.scale(-1, 1);
    }
    context.fillStyle = background;
    context.fillRect(0, 0, 512, 192);
    context.font = '600 82px sans-serif';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.fillStyle = foreground;
    context.fillText(text.length > 10 ? `${text.slice(0, 9)}…` : text, 256, 96, 470);
    texture.update();
    const material = new StandardMaterial(`label-material-${text}`, this.scene);
    material.diffuseTexture = texture;
    material.emissiveColor = new Color3(0.2, 0.2, 0.2);
    material.specularColor = Color3.Black();
    material.backFaceCulling = false;
    const plane = MeshBuilder.CreatePlane(`label-plane-${text}`, { width, height }, this.scene);
    plane.parent = parent;
    plane.position = new Vector3(...position);
    plane.material = material;
    owned.push(texture, material);
    return plane;
  }

  plant(parent, x, z, scale = 1) {
    // 陶土花盆(带托盘 + 翻边)
    const saucer = this.box('plant-saucer', { width: 0.5 * scale, height: 0.04, depth: 0.5 * scale }, [x, 0.02, z], '#a87762', parent, false);
    const pot = MeshBuilder.CreateCylinder('terracotta-pot', { height: 0.4 * scale, diameterTop: 0.48 * scale, diameterBottom: 0.36 * scale, tessellation: 14 }, this.scene);
    pot.position = new Vector3(x, 0.24 * scale, z);
    pot.parent = parent;
    pot.material = this.material('#c49177');
    this.shadows.addShadowCaster(pot);
    const rim = this.box('pot-rim', { width: 0.5 * scale, height: 0.05 * scale, depth: 0.5 * scale }, [x, 0.46 * scale, z], '#b07a5e', parent, false);
    // 土壤
    this.box('pot-soil', { width: 0.42 * scale, height: 0.03, depth: 0.42 * scale }, [x, 0.44 * scale, z], '#5b4632', parent, false);
    // 叶片簇(5 层,大小递减 + 颜色变化)
    const leafColors = ['#7e9f79', '#8eaf85', '#a7bf91', '#6f8d6a', '#93b18a'];
    const leafSpecs = [
      { dy: 0.62, dx: 0, dz: 0, r: 0.32, s: [1.4, 0.9, 1.4], c: 0 },
      { dy: 0.74, dx: -0.18, dz: 0.08, r: 0.26, s: [1.2, 0.8, 1.2], c: 1 },
      { dy: 0.72, dx: 0.18, dz: -0.06, r: 0.26, s: [1.2, 0.85, 1.2], c: 2 },
      { dy: 0.86, dx: 0.05, dz: 0.18, r: 0.22, s: [1, 0.7, 1.1], c: 3 },
      { dy: 0.88, dx: -0.1, dz: -0.12, r: 0.2, s: [0.95, 0.7, 1.05], c: 4 },
    ];
    for (const leaf of leafSpecs) {
      this.sphere('round-leaves', leaf.r * scale, [x + leaf.dx * scale, leaf.dy * scale, z + leaf.dz * scale], leafColors[leaf.c], parent, leaf.s);
    }
    // 顶端小花苞
    this.sphere('plant-bud', 0.09 * scale, [x, 1.04 * scale, z], '#e8a9a0', parent, [1, 0.7, 1]);
    return pot;
  }

  readingNook(x, z) {
    // 圆形橡木桌 + 桌裙
    const table = MeshBuilder.CreateCylinder('round-reading-table', { height: 0.16, diameter: 2.15, tessellation: 32 }, this.scene);
    table.position = new Vector3(x, 0.84, z);
    table.material = this.material(WOOD.oak);
    this.shadows.addShadowCaster(table);
    const tableSkirt = MeshBuilder.CreateCylinder('table-skirt', { height: 0.12, diameterTop: 2.1, diameterBottom: 1.9, tessellation: 32 }, this.scene);
    tableSkirt.position = new Vector3(x, 0.7, z);
    tableSkirt.parent = table;
    tableSkirt.material = this.material(WOOD.walnut);
    this.shadows.addShadowCaster(tableSkirt);
    for (const legX of [-0.55, 0.55]) for (const legZ of [-0.55, 0.55]) {
      const leg = this.box('table-leg', { width: 0.14, height: 0.7, depth: 0.14 }, [legX, -0.42, legZ], WOOD.walnut, table);
      const foot = this.box('table-foot', { width: 0.18, height: 0.04, depth: 0.18 }, [legX, -0.77, legZ], WOOD.ebony, table, false);
    }
    // 桌上一摞翻开的书 + 小台灯
    const openBookL = this.box('open-book-left', { width: 0.38, height: 0.04, depth: 0.52 }, [-0.18, 0.11, -0.05], '#fff0cf', table);
    const openBookR = this.box('open-book-right', { width: 0.38, height: 0.04, depth: 0.52 }, [0.18, 0.11, -0.05], '#fff0cf', table);
    const bookSpine = this.box('open-book-spine', { width: 0.05, height: 0.05, depth: 0.52 }, [0, 0.115, -0.05], '#a8855a', table, false);
    for (const line of [-0.16, -0.05, 0.06, 0.17]) {
      this.box('printed-page-line', { width: 0.3, height: 0.004, depth: 0.018 }, [-0.18, 0.14, line], '#c7b997', table, false);
      this.box('printed-page-line', { width: 0.3, height: 0.004, depth: 0.018 }, [0.18, 0.14, line], '#c7b997', table, false);
    }
    // 桌角一摞合上的书
    const stackColors = [BOOK_COLORS[0], BOOK_COLORS[3], BOOK_COLORS[1]];
    for (let i = 0; i < 3; i += 1) {
      const stackBook = this.box('stacked-book', { width: 0.42 - i * 0.02, height: 0.05, depth: 0.3 - i * 0.01 },
        [0.65 + i * 0.005, 0.105 + i * 0.05, 0.45 + i * 0.005], stackColors[i], table);
      this.box('stacked-page', { width: 0.4 - i * 0.02, height: 0.048, depth: 0.005 },
        [0.65 + i * 0.005, 0.105 + i * 0.05, 0.6 + i * 0.005], '#fff5da', stackBook, false);
    }
    // 小台灯(在书堆旁,发出暖光)
    const lampBase = this.box('lamp-base', { width: 0.18, height: 0.04, depth: 0.18 }, [0.6, 0.11, -0.55], WOOD.ebony, table, false);
    const lampStem = this.box('lamp-stem', { width: 0.05, height: 0.4, depth: 0.05 }, [0.6, 0.32, -0.55], WOOD.ebony, table, false);
    const lampShade = MeshBuilder.CreateCylinder('lamp-shade', { height: 0.22, diameterTop: 0.12, diameterBottom: 0.28, tessellation: 18 }, this.scene);
    lampShade.position = new Vector3(0.6, 0.55, -0.55);
    lampShade.parent = table;
    lampShade.material = this.material('#d4a050');
    this.shadows.addShadowCaster(lampShade);
    const lampBulb = this.sphere('lamp-bulb', 0.1, [0.6, 0.5, -0.55], '#fff0c5', table, [1, 0.7, 1]);
    const lampLight = new PointLight('reading-lamp-light', new Vector3(0.6, 0.5, -0.55), this.scene);
    lampLight.parent = table;
    lampLight.intensity = 0.6;
    lampLight.diffuse = Color3.FromHexString('#ffd9a0');
    lampLight.specular = Color3.FromHexString('#ffd9a0');
    lampLight.range = 5;
    // 灯具本体入环境,灯光挂在桌上由 table.dispose() 递归回收
    this.environment.push(lampBase, lampStem, lampShade, lampBulb);
    // 两把椅子(带软垫 + 椅背) -----------------------------
    for (const direction of [-1, 1]) {
      const cushion = MeshBuilder.CreateCylinder('round-cushion', { height: 0.16, diameter: 0.78, tessellation: 22 }, this.scene);
      cushion.parent = table;
      cushion.position = new Vector3(direction * 1.65, -0.32, 0);
      cushion.material = this.material(direction < 0 ? '#9bb8a0' : '#d9b299');
      this.shadows.addShadowCaster(cushion);
      // 椅背(扁球 + 顶饰)
      const back = this.sphere('soft-chair-back', 0.78, [direction * 1.95, 0.12, 0], direction < 0 ? '#9bb8a0' : '#d9b299', table, [0.22, 0.95, 1]);
      const backTop = this.sphere('chair-back-finial', 0.18, [direction * 1.95, 0.5, 0], direction < 0 ? '#86a48b' : '#c79e87', table, [1, 0.6, 1]);
      // 椅腿
      for (const side of [-1, 1]) {
        this.box('chair-leg', { width: 0.12, height: 0.43, depth: 0.12 }, [direction * 1.65, -0.6, side * 0.26], WOOD.walnut, table);
        const foot = this.box('chair-foot', { width: 0.15, height: 0.03, depth: 0.15 }, [direction * 1.65, -0.82, side * 0.26], WOOD.ebony, table, false);
      }
      // 椅背立柱
      for (const side of [-1, 1]) {
        this.box('chair-back-post', { width: 0.05, height: 0.5, depth: 0.05 }, [direction * 1.95, 0.25, side * 0.18], WOOD.walnut, table);
      }
    }
    return table;
  }

  /**
   * 林间图书馆中的「沉思者」石像 — 致敬罗丹的《思考者》(Le Penseur):
   * 坐于岩床,上身前倾,右肘支于左膝,右手托腮,低头凝神;
   * 左臂搁在左膝,双脚踏实,肌肉感以低面体暗示。
   * 整组网格挂到 root 命中盒上,metadata.thinker=true 触发点击开对话。
   */
  thinkerStatue(x, z) {
    const root = this.box('thinker-statue', { width: 1.5, height: 2.0, depth: 1.5 }, [x, 1.0, z], STONE.mid, null, false);
    root.metadata = { thinker: true };
    // 让石像正面朝向相机;同时铭牌贴图需要水平镜像
    root.rotation.y = Math.PI;
    const owned = [];
    const { light: sL, mid: sM, dark: sD, shadow: sS } = STONE;

    // ─── 底座(基座 + 顶板) ───────────────────────────
    const pedestal = MeshBuilder.CreateCylinder('thinker-pedestal', {
      height: 0.36, diameterTop: 1.0, diameterBottom: 1.2, tessellation: 18,
    }, this.scene);
    pedestal.position = new Vector3(0, -0.8, 0);
    pedestal.parent = root;
    pedestal.material = this.material(sL);
    this.shadows.addShadowCaster(pedestal);
    const pedestalBase = MeshBuilder.CreateCylinder('thinker-pedestal-base', {
      height: 0.1, diameter: 1.3, tessellation: 18,
    }, this.scene);
    pedestalBase.position = new Vector3(0, -1.0, 0);
    pedestalBase.parent = root;
    pedestalBase.material = this.material(sD);
    this.shadows.addShadowCaster(pedestalBase);
    // 顶板(承托人物坐姿)
    const slab = this.box('thinker-slab', { width: 1.0, height: 0.1, depth: 0.9 }, [0, -0.55, 0], sM, root, false);
    const slabTop = this.box('thinker-slab-top', { width: 0.9, height: 0.06, depth: 0.8 }, [0, -0.47, 0], sL, root, false);

    // ─── 双脚(踩在地面,在底座前方) ─────────────────
    // 右脚(在底座前方,支起右膝)
    const rightFoot = this.box('thinker-right-foot', { width: 0.3, height: 0.12, depth: 0.45 }, [0.04, -0.94, 0.5], sD, root);
    this.box('right-toes', { width: 0.28, height: 0.04, depth: 0.1 }, [0.04, -0.88, 0.68], sS, root, false);
    // 左脚
    const leftFoot = this.box('thinker-left-foot', { width: 0.28, height: 0.12, depth: 0.42 }, [-0.22, -0.94, 0.45], sD, root);
    this.box('left-toes', { width: 0.26, height: 0.04, depth: 0.1 }, [-0.22, -0.88, 0.62], sS, root, false);

    // ─── 双腿(右膝抬起承肘,左腿较缓) ────────────────
    // 右大腿:从髋部向前往上抬到右膝(右肘将架在此处)
    const rightThigh = this.box('thinker-right-thigh', { width: 0.28, height: 0.4, depth: 0.32 }, [0.04, -0.32, 0.12], sM, root);
    rightThigh.rotation.x = -1.05;
    const rightKnee = this.sphere('thinker-right-knee', 0.3, [0.04, -0.28, 0.3], sL, root, [1, 0.95, 1.15]);
    // 右小腿:从膝盖斜下到脚
    const rightShin = this.box('thinker-right-shin', { width: 0.22, height: 0.7, depth: 0.26 }, [0.04, -0.6, 0.4], sM, root);
    rightShin.rotation.x = -0.4;

    // 左大腿(向下并稍向前)
    const leftThigh = this.box('thinker-left-thigh', { width: 0.26, height: 0.36, depth: 0.3 }, [-0.22, -0.55, 0.1], sM, root);
    leftThigh.rotation.x = -0.7;
    const leftKnee = this.sphere('thinker-left-knee', 0.28, [-0.22, -0.68, 0.22], sL, root, [1, 0.95, 1.15]);
    const leftShin = this.box('thinker-left-shin', { width: 0.2, height: 0.4, depth: 0.24 }, [-0.22, -0.84, 0.32], sM, root);
    leftShin.rotation.x = -0.8;

    // ─── 躯干(髋 → 腰 → 胸,前倾逐渐加大) ────────────
    const hips = this.box('thinker-hips', { width: 0.6, height: 0.28, depth: 0.48 }, [0, -0.32, 0.02], sM, root);
    hips.rotation.x = 0.18;
    const lowerTorso = this.box('thinker-lower-torso', { width: 0.6, height: 0.32, depth: 0.42 }, [0, -0.06, 0.06], sM, root);
    lowerTorso.rotation.x = 0.32;
    const upperTorso = this.box('thinker-upper-torso', { width: 0.58, height: 0.42, depth: 0.38 }, [0, 0.2, 0.12], sM, root);
    upperTorso.rotation.x = 0.48;
    // 腹直肌(一道竖向刻痕)
    this.box('thinker-abdomen-line', { width: 0.04, height: 0.28, depth: 0.005 }, [0, 0.04, 0.32], sD, root, false);
    // 胸肌(两块薄板暗示体积)
    this.box('thinker-pec-l', { width: 0.22, height: 0.18, depth: 0.06 }, [-0.12, 0.24, 0.3], sL, root, false);
    this.box('thinker-pec-r', { width: 0.22, height: 0.18, depth: 0.06 }, [0.12, 0.24, 0.3], sL, root, false);
    // 背(圆弧感)
    const back = this.box('thinker-back', { width: 0.5, height: 0.55, depth: 0.2 }, [0, 0.18, -0.14], sM, root, false);
    back.rotation.x = -0.12;
    // 肩胛骨(两片斜方)
    this.box('thinker-scapula-l', { width: 0.2, height: 0.18, depth: 0.04 }, [-0.16, 0.32, -0.12], sD, root, false);
    this.box('thinker-scapula-r', { width: 0.2, height: 0.18, depth: 0.04 }, [0.16, 0.32, -0.12], sD, root, false);

    // ─── 肩部 + 颈 + 头(低头凝神) ───────────────────
    const shoulders = this.sphere('thinker-shoulders', 0.55, [0, 0.46, 0.04], sM, root, [1.25, 0.55, 0.95]);
    // 斜方肌(更厚实的脖子底座)
    this.box('thinker-trapezius', { width: 0.42, height: 0.12, depth: 0.22 }, [-0.04, 0.58, 0.08], sM, root, false);
    const neck = this.box('thinker-neck', { width: 0.2, height: 0.18, depth: 0.2 }, [-0.04, 0.66, 0.16], sM, root);
    neck.rotation.x = 0.55;
    // 头(缩小,更符合人体比例 — 原 0.44 太大)
    const head = this.sphere('thinker-head', 0.27, [-0.04, 0.86, 0.18], sL, root, [1, 1.15, 1.08]);
    head.rotation.x = 0.55;
    // 眉骨(凸起的弧形)
    this.sphere('thinker-brow', 0.13, [-0.04, 0.95, 0.4], sD, root, [1.6, 0.25, 0.4]);
    // 鼻梁(更明显的隆起)
    this.box('thinker-nose-bridge', { width: 0.04, height: 0.14, depth: 0.05 }, [-0.04, 0.86, 0.43], sM, root, false);
    this.sphere('thinker-nose-tip', 0.035, [-0.04, 0.82, 0.44], sD, root);
    // 眼窝(深陷,两块小方块模拟阴影)
    this.box('thinker-eye-l', { width: 0.07, height: 0.03, depth: 0.015 }, [-0.1, 0.9, 0.4], sD, root, false);
    this.box('thinker-eye-r', { width: 0.07, height: 0.03, depth: 0.015 }, [0.02, 0.9, 0.4], sD, root, false);
    // 嘴(一道横向凹线)
    this.box('thinker-mouth', { width: 0.1, height: 0.012, depth: 0.015 }, [-0.04, 0.78, 0.4], sD, root, false);
    // 颧骨(两块圆)
    this.sphere('thinker-cheek-l', 0.05, [-0.14, 0.85, 0.36], sL, root);
    this.sphere('thinker-cheek-r', 0.05, [0.06, 0.85, 0.36], sL, root);
    // 头顶发髻
    const hair = this.sphere('thinker-hair', 0.2, [-0.04, 1.04, 0.08], sD, root, [1, 0.7, 1]);
    // 后脑勺(更圆)
    this.sphere('thinker-skull-back', 0.13, [-0.04, 0.92, -0.02], sM, root, [1.1, 1, 0.9]);

    // ─── 膝上垂布(沉思者标志性的那块布) ────────────────
    // 主布面:从腰部斜披到大腿,扁长方体 + 略向前倾
    const drape = this.box('thinker-drape-main', { width: 0.85, height: 0.06, depth: 0.62 }, [-0.06, -0.18, 0.18], sD, root);
    drape.rotation.x = 0.32; // 前倾,使布面斜搭在双膝上
    // 左侧布褶(更厚实的堆积,Rodin 原雕像特征)
    this.box('thinker-drape-fold-1', { width: 0.28, height: 0.1, depth: 0.5 }, [-0.32, -0.16, 0.2], sM, root);
    this.box('thinker-drape-fold-2', { width: 0.22, height: 0.08, depth: 0.45 }, [-0.36, -0.08, 0.16], sM, root, false);
    // 右侧垂下的布边(盖住右腿外侧)
    this.box('thinker-drape-edge', { width: 0.18, height: 0.28, depth: 0.5 }, [0.3, -0.32, 0.16], sD, root);
    this.box('thinker-drape-edge-fold', { width: 0.14, height: 0.06, depth: 0.5 }, [0.32, -0.18, 0.16], sD, root, false);
    // 布面纹理(几道细线模拟褶皱)
    for (let i = 0; i < 3; i += 1) {
      this.box(`drape-crease-${i}`, { width: 0.7, height: 0.005, depth: 0.005 }, [-0.06, -0.16 + i * 0.05, 0.45 + i * 0.04], sS, root, false);
    }
    // ─── 右臂(肘在右膝,前臂上举托下巴) ──────────────
    // 上臂:从右肩斜向左下到右膝上方,长度 0.56
    const rightUpperArm = this.box('thinker-right-upper-arm', { width: 0.17, height: 0.56, depth: 0.17 }, [0.12, -0.04, 0.18], sM, root);
    rightUpperArm.rotation.z = -0.29;
    rightUpperArm.rotation.x = -0.48;
    // 肱二头肌(鼓起)
    this.sphere('thinker-bicep', 0.11, [0.16, 0.08, 0.16], sM, root, [1.1, 1.1, 1.1]);
    // 右肘(正落在右膝上)
    const rightElbow = this.sphere('thinker-right-elbow', 0.18, [0.04, -0.28, 0.3], sD, root);
    // 前臂:从肘部几乎垂直上升到下巴(0.04, -0.28, 0.3) → (-0.04, 0.8, 0.32)
    const rightForearm = this.box('thinker-right-forearm', { width: 0.12, height: 1.08, depth: 0.12 }, [0.0, 0.26, 0.31], sM, root);
    rightForearm.rotation.x = -0.02;
    rightForearm.rotation.z = -0.07;
    // 前臂肌肉(小臂鼓起一块,让前臂不只是一根棍)
    this.sphere('thinker-forearm-bulk', 0.09, [0.0, 0.1, 0.31], sM, root, [1, 1, 1.2]);
    // 右手(贴在下巴处)
    const rightHand = this.sphere('thinker-right-hand', 0.16, [-0.04, 0.8, 0.32], sL, root, [1.1, 0.9, 1.1]);
    // 食指(勾住下颌)
    this.box('thinker-finger-1', { width: 0.04, height: 0.04, depth: 0.1 }, [-0.04, 0.83, 0.36], sM, root, false);
    this.box('thinker-finger-2', { width: 0.04, height: 0.035, depth: 0.08 }, [0.02, 0.78, 0.36], sM, root, false);
    // 下巴(小一点,贴在新头部下缘)
    const chin = this.sphere('thinker-chin', 0.11, [-0.04, 0.78, 0.32], sL, root, [0.9, 0.8, 1.1]);

    // ─── 左臂(自然垂在身体左侧,小臂搭在左膝) ─────────
    // 上臂从左肩下垂到左肘
    const leftUpperArm = this.box('thinker-left-upper-arm', { width: 0.16, height: 0.5, depth: 0.16 }, [-0.3, 0.05, 0.1], sM, root);
    leftUpperArm.rotation.z = 0.45;
    leftUpperArm.rotation.x = 0.55;
    const leftElbow = this.sphere('thinker-left-elbow', 0.18, [-0.3, -0.32, 0.32], sD, root);
    // 前臂从左肘斜搭到左膝(-0.22, -0.68, 0.22) → 膝附近
    const leftForearm = this.box('thinker-left-forearm', { width: 0.14, height: 0.5, depth: 0.14 }, [-0.28, -0.52, 0.28], sM, root);
    leftForearm.rotation.x = 0.4;
    leftForearm.rotation.z = -0.18;
    const leftHand = this.box('thinker-left-hand', { width: 0.18, height: 0.14, depth: 0.24 }, [-0.22, -0.72, 0.24], sD, root);

    // ─── 底座铭牌 ─────────────────────────────────
    const plaque = this.box('thinker-plaque', { width: 0.65, height: 0.22, depth: 0.06 }, [0, -0.8, 0.58], sS, root, false);
    this.label('问书 · Thinker', root, [0, -0.8, 0.62], 0.85, 0.22, owned, '#cab9a0', '#3d3527', true);

    return {
      root,
      owned,
      parts: [
        pedestal, pedestalBase, slab, slabTop,
        rightFoot, rightShin, rightThigh, rightKnee,
        leftFoot, leftShin, leftThigh, leftKnee,
        hips, lowerTorso, upperTorso, back,
        shoulders, neck, head, hair,
        rightUpperArm, rightElbow, rightForearm, rightHand, chin,
        leftUpperArm, leftElbow, leftForearm, leftHand,
        plaque,
      ],
    };
  }

  setAreas(areas, booksByArea) {
    this.clearHover();
    for (const region of this.regions.values()) this.disposeRegion(region);
    this.regions.clear();
    if (this.thinker) {
      for (const mesh of this.thinker.parts) { this.shadows.removeShadowCaster(mesh, true); mesh.dispose(); }
      for (const resource of this.thinker.owned) resource.dispose();
      this.thinker.root.dispose(false, false);
      this.thinker = null;
    }
    for (const mesh of this.environment) { this.shadows.removeShadowCaster(mesh, true); mesh.dispose(); }
    this.environment = [];
    const xs = areas.map((area) => area.position.x);
    const zs = areas.map((area) => area.position.z);
    const minX = Math.min(-3, ...xs) - 3.2;
    const maxX = Math.max(3, ...xs) + 3.2;
    const minZ = Math.min(0, ...zs) - 5.7;
    const maxZ = Math.max(0, ...zs) + 3;
    const center = new Vector3((minX + maxX) / 2, 0.7, (minZ + maxZ) / 2);
    const width = maxX - minX;
    const depth = maxZ - minZ;
    this.overview = { target: center, radius: Math.max(15, width * 1.1, depth * 1.7), alpha: -Math.PI / 2 - 0.25, beta: 0.87 };
    // 地板:基座 + 细分木板(4 种暖木色交替) + 边沿踢脚
    const floor = this.box('wooden-platform', { width, height: 0.35, depth }, [center.x, -0.25, center.z], WOOD.cherry, null, false);
    this.environment.push(floor);
    const plankColors = [WOOD.oak, WOOD.walnut, '#d4ad7a', '#a8825b', WOOD.oak];
    const plankWidth = 0.4;
    for (let x = minX; x < maxX; x += plankWidth) {
      const actualWidth = Math.min(plankWidth, maxX - x);
      const colorIndex = Math.abs(Math.round(x * 10)) % plankColors.length;
      this.environment.push(this.box('floor-plank', { width: actualWidth - 0.02, height: 0.05, depth: depth - 0.12 }, [x + actualWidth / 2, -0.05, center.z], plankColors[colorIndex], null, false));
    }
    // 踢脚线(沿后墙底部)
    this.environment.push(this.box('baseboard', { width, height: 0.12, depth: 0.05 }, [center.x, 0.06, maxZ - 0.08], WOOD.ebony, null, false));
    // 后墙:主体 + 顶冠 + 横向腰线
    this.environment.push(this.box('back-wall', { width, height: 1.4, depth: 0.2 }, [center.x, 0.65, maxZ], '#eee1c5', null, false));
    this.environment.push(this.box('wall-wainscot', { width, height: 0.6, depth: 0.04 }, [center.x, 0.32, maxZ - 0.12], '#e0d4b8', null, false));
    this.environment.push(this.box('wall-cap', { width: width + 0.2, height: 0.12, depth: 0.3 }, [center.x, 1.4, maxZ], '#b5c9ae', null, false));
    this.environment.push(this.box('wall-crown', { width: width + 0.3, height: 0.06, depth: 0.32 }, [center.x, 1.49, maxZ], '#9bb89e', null, false));
    // 后墙上的相框(致敬沉思者)
    this.environment.push(this.box('wall-frame-outer', { width: 0.8, height: 1.0, depth: 0.04 }, [center.x - width * 0.3, 0.95, maxZ - 0.14], WOOD.walnut, null, false));
    this.environment.push(this.box('wall-frame-inner', { width: 0.66, height: 0.86, depth: 0.005 }, [center.x - width * 0.3, 0.95, maxZ - 0.165], '#d8e0c5', null, false));
    // 画中风景:天空 + 山 + 树
    this.environment.push(this.box('wall-painting-sky', { width: 0.66, height: 0.5, depth: 0.001 }, [center.x - width * 0.3, 1.12, maxZ - 0.16], '#cdd9c5', null, false));
    this.environment.push(this.box('wall-painting-mountain', { width: 0.5, height: 0.25, depth: 0.002 }, [center.x - width * 0.3 - 0.05, 0.92, maxZ - 0.159], '#9ba68b', null, false));
    this.environment.push(this.box('wall-painting-mountain-2', { width: 0.4, height: 0.2, depth: 0.002 }, [center.x - width * 0.3 + 0.1, 0.88, maxZ - 0.158], '#a8b496', null, false));
    this.environment.push(this.box('wall-painting-ground', { width: 0.66, height: 0.18, depth: 0.001 }, [center.x - width * 0.3, 0.66, maxZ - 0.16], '#c2b294', null, false));
    this.environment.push(this.sphere('wall-painting-tree', 0.14, [center.x - width * 0.3 - 0.18, 0.85, maxZ - 0.155], '#7e9f79', null, [1, 1.2, 0.5]));
    this.environment.push(this.box('wall-painting-trunk', { width: 0.04, height: 0.16, depth: 0.002 }, [center.x - width * 0.3 - 0.18, 0.74, maxZ - 0.157], '#6e5238', null, false));
    // 两侧盆栽
    for (const x of [minX + 1.2, maxX - 1.2]) {
      const pot = this.plant(null, x, maxZ - 0.7, 1.5);
      this.environment.push(pot, ...this.scene.meshes.filter((mesh) => mesh.name === 'round-leaves' && !mesh.parent && Math.abs(mesh.position.x - x) < 0.4));
    }
    // 阅读桌 + 思考者石像
    this.environment.push(this.readingNook(center.x, minZ + 1.65));
    this.thinker = this.thinkerStatue(center.x + 2.4, minZ + 1.65);
    for (const area of areas) this.addArea(area, booksByArea[area.id] || []);
    this.setEditing(this.editing);
    this.focus(this.activeId);
    // ── 关键:把"永远不动"的网格冻结,省下每帧的世界矩阵重算 + 材质 uniform 上传 ──
    //  this.environment 里装的就是这类:墙、地板、踢脚、画框、桌、椅、灯、盆栽 ——
    //  它们的 parent=null 且永远不会改 transform。region-N 也在 parent=null,但它是
    //  可拖动的书架容器,绝对不能冻结,所以我们只冻结 environment 列表里的网格。
    //  thinker 同样 parent=null 且不动(可点击但不会跑),一起冻结。
    for (const mesh of this.environment) {
      if (!mesh.isDisposed()) {
        mesh.freezeWorldMatrix();
        // 不进 frustum culling 投票:环境都是不可见大块,关掉它省一轮 BVH 遍历
        mesh.alwaysSelectAsActiveMesh = true;
      }
    }
    if (this.thinker && !this.thinker.root.isDisposed()) {
      // thinker 是一组父子链,逐个冻结:它们都相对 root 静止
      for (const part of this.thinker.parts) {
        if (!part.isDisposed()) {
          part.freezeWorldMatrix();
          part.alwaysSelectAsActiveMesh = true;
        }
      }
    }
    // 材质冻结:StandardMaterial 不会改 diffuseColor / specularColor,每帧上传 uniform
    // 就是浪费;freeze() 告诉 Babylon 跳过这个 mesh 的绑定阶段
    for (const material of this.materials.values()) material.freeze();
    // 头几帧强制 render,把新场景画出来再进入"静止可跳帧"模式
    this._framesToForce = 3;
  }

  addArea(area, books) {
    const root = this.box(`region-${area.id}`, { width: 4.4, height: 0.09, depth: 3.6 }, [area.position.x, 0.05, area.position.z], area.color, null, false);
    root.metadata = { areaId: area.id };
    const owned = [];
    const region = { root, owned, bookMeshes: [] };
    this.regions.set(area.id, region);
    // 地毯:外圈深色 + 内圈浅色
    this.box('rug-border', { width: 4.4, height: 0.005, depth: 3.6 }, [0, 0.05, 0], area.color, root, false);
    this.box('rug-inset', { width: 4.0, height: 0.012, depth: 3.2 }, [0, 0.054, 0], '#f2e8cf', root, false);
    this.box('rug-pattern', { width: 3.6, height: 0.014, depth: 2.8 }, [0, 0.058, 0], '#e6dcc1', root, false);
    // 书架背板(双层,前后错位形成层次)
    this.box('shelf-back', { width: 3.55, height: 3.0, depth: 0.1 }, [0, 1.57, 0.7], '#bd956e', root);
    this.box('shelf-back-panel', { width: 3.35, height: 2.8, depth: 0.04 }, [0, 1.57, 0.66], '#d5b18a', root, false);
    // 侧板(带顶部弧形装饰)
    for (const x of [-1.78, 1.78]) {
      this.box('rounded-shelf-side', { width: 0.16, height: 3.1, depth: 0.85 }, [x, 1.55, 0.3], '#caa27c', root);
      // 侧板顶部雕花(小球 + 圆环)
      this.sphere('shelf-finial', 0.18, [x, 3.12, 0.3], '#caa27c', root);
      this.sphere('shelf-finial-cap', 0.1, [x, 3.24, 0.3], '#9c7a58', root);
      // 侧板中部凹槽(浅刻)
      this.box('shelf-side-trim', { width: 0.18, height: 0.04, depth: 0.85 }, [x, 1.4, 0.3], '#9c7a58', root, false);
      this.box('shelf-side-trim-2', { width: 0.18, height: 0.04, depth: 0.85 }, [x, 0.4, 0.3], '#9c7a58', root, false);
    }
    // 底座踢脚线
    this.box('shelf-baseboard', { width: 3.7, height: 0.18, depth: 0.95 }, [0, 0.13, 0.27], '#9c7a58', root);
    // 4 层隔板 + 顶层冠饰(双层冠顶 + 边沿线条)
    for (let row = 0; row < 4; row += 1) {
      this.box('shelf-board', { width: 3.65, height: 0.14, depth: 0.9 }, [0, 0.22 + row * 0.88, 0.27], '#d5b18a', root);
      // 隔板前缘压条
      this.box('shelf-board-edge', { width: 3.65, height: 0.04, depth: 0.04 }, [0, 0.22 + row * 0.88, 0.69], '#b08a5e', root, false);
    }
    // 顶冠(双层 + 收边线条)
    this.box('shelf-crown', { width: 3.95, height: 0.18, depth: 1.0 }, [0, 3.05, 0.27], '#d9b994', root);
    this.box('shelf-cornice', { width: 4.0, height: 0.08, depth: 1.05 }, [0, 3.18, 0.27], '#b08a5e', root, false);
    this.box('shelf-cornice-top', { width: 4.05, height: 0.05, depth: 1.08 }, [0, 3.24, 0.27], '#9c7a58', root, false);
    // 区域名牌 + 书本计数牌
    this.label(area.name, root, [0, 3.1, -0.25], 2.6, 0.4, owned);
    this.label(`${area.count || 0} 本书`, root, [0, 0.32, -1.3], 1.3, 0.34, owned, area.color, '#fffdf5');
    // 左侧盆栽
    this.plant(root, 1.65, -0.9, 0.7);
    // 顶层冠饰上的小物件:小地球仪 / 钟 / 花瓶
    const topY = 3.18;
    this.sphere('mini-globe', 0.18, [-1.4, topY, 0.27], '#5b8aa3', root, [1, 1, 1]);
    this.box('mini-globe-stand', { width: 0.1, height: 0.04, depth: 0.1 }, [-1.4, 3.0, 0.27], '#5d4126', root, false);
    // 钟
    this.box('mini-clock', { width: 0.22, height: 0.22, depth: 0.1 }, [1.4, topY - 0.05, 0.27], '#5d4126', root, false);
    this.sphere('mini-clock-face', 0.09, [1.4, topY - 0.05, 0.21], '#f7edd7', root, [1, 1, 0.3]);
    // 花瓶
    const vase = MeshBuilder.CreateCylinder('mini-vase', { height: 0.18, diameterTop: 0.1, diameterBottom: 0.14, tessellation: 12 }, this.scene);
    vase.position = new Vector3(0.9, topY - 0.05, 0.27);
    vase.parent = root;
    vase.material = this.material('#7e9e92');
    this.shadows.addShadowCaster(vase);
    this.sphere('vase-flower', 0.08, [0.9, topY + 0.08, 0.27], '#e8a9a0', root, [1, 0.8, 1]);
    // 顶层斜放一本摊开的画册
    this.box('top-lean-book-base', { width: 0.5, height: 0.04, depth: 0.6 }, [0, topY - 0.04, 0.27], BOOK_COLORS[2], root);
    this.box('top-lean-book-page', { width: 0.46, height: 0.005, depth: 0.56 }, [0, topY - 0.02, 0.27], '#fff0cf', root, false);
    // 滑轨梯子
    this.box('ladder-rail', { width: 3.7, height: 0.04, depth: 0.06 }, [0, 3.32, 0.85], '#5d4126', root, false);
    // 梯子本体(挂在滑轨上,半透明斜挂)
    for (let step = 0; step < 5; step += 1) {
      this.box(`ladder-step-${step}`, { width: 0.55, height: 0.04, depth: 0.08 }, [0, 3.32 - step * 0.42, 0.92], '#9c6f44', root, false);
    }
    this.box('ladder-rail-left', { width: 0.06, height: 1.95, depth: 0.08 }, [-0.28, 2.35, 0.92], '#9c6f44', root, false);
    this.box('ladder-rail-right', { width: 0.06, height: 1.95, depth: 0.08 }, [0.28, 2.35, 0.92], '#9c6f44', root, false);
    // 挂轨到梯子的吊环
    for (const side of [-0.28, 0.28]) {
      this.sphere(`ladder-hanger-${side}`, 0.05, [side, 3.28, 0.88], '#5d4126', root);
    }
    // 各层书架的内容 — 6 本书为主,部分层放装饰品 + 部分书斜放
    for (let row = 0; row < 4; row += 1) {
      const yBase = 0.32 + row * 0.88;
      const layerBooks = books.slice(row * 6, (row + 1) * 6);
      this.populateShelf(root, region, area, yBase, layerBooks, row);
    }
    // 拖动行为
    const drag = new PointerDragBehavior({ dragPlaneNormal: Vector3.Up() });
    drag.useObjectOrientationForDragging = false;
    drag.onDragStartObservable.add(() => { this.dragging = true; this.clearHover(); });
    drag.onDragEndObservable.add(() => {
      const position = { x: Math.max(-32, Math.min(32, Math.round(root.position.x * 2) / 2)), z: Math.max(-32, Math.min(32, Math.round(root.position.z * 2) / 2)) };
      root.position.x = position.x;
      root.position.z = position.z;
      this.callbacks.onMove(area.id, position);
      window.setTimeout(() => { this.dragging = false; }, 0);
    });
    drag.enabled = this.editing;
    root.addBehavior(drag);
    region.drag = drag;
  }

  // 填充单层书架:书本居中,留白处放一个摆件
  populateShelf(root, region, area, yBase, books, rowIndex) {
    // 空层:不显示任何书本或假书,保持书架干净
    if (books.length === 0) return;
    const slotWidth = 0.5;
    const numBooks = Math.min(books.length, 6);
    // 让 N 本书在 6 个槽位宽度的中间居中
    const startX = -((numBooks - 1) * slotWidth) / 2;
    for (let i = 0; i < numBooks; i += 1) {
      const book = books[i];
      const xPos = startX + i * slotWidth;
      this.addShelfBook(root, region, area, book, xPos, yBase);
    }
    // 书本右侧(仍有空位)放一个摆件
    if (numBooks < 6) {
      const decorX = startX + numBooks * slotWidth + 0.45;
      this.addShelfDecor(root, region, yBase, rowIndex, decorX);
    }
  }

  // 单层摆件:每层一种,统一调用
  addShelfDecor(root, region, yBase, rowIndex, xPos) {
    if (rowIndex === 0) {
      // 顶层:小相框
      this.box('shelf-photo-frame', { width: 0.32, height: 0.32, depth: 0.04 }, [xPos, yBase + 0.42, 0.5], WOOD.walnut, root, false);
      this.box('shelf-photo-inner', { width: 0.26, height: 0.26, depth: 0.005 }, [xPos, yBase + 0.42, 0.48], '#d8e0c5', root, false);
    } else if (rowIndex === 1) {
      // 第二层:沙漏
      const hourglass = MeshBuilder.CreateCylinder('shelf-hourglass-top', { height: 0.16, diameterTop: 0.12, diameterBottom: 0.02, tessellation: 10 }, this.scene);
      hourglass.position = new Vector3(xPos, yBase + 0.36, 0.45);
      hourglass.parent = root;
      hourglass.material = this.material('#e8d8b0');
      this.shadows.addShadowCaster(hourglass);
      const hourglassBottom = MeshBuilder.CreateCylinder('shelf-hourglass-bottom', { height: 0.16, diameterTop: 0.02, diameterBottom: 0.12, tessellation: 10 }, this.scene);
      hourglassBottom.position = new Vector3(xPos, yBase + 0.18, 0.45);
      hourglassBottom.parent = root;
      hourglassBottom.material = this.material('#e8d8b0');
      this.shadows.addShadowCaster(hourglassBottom);
      this.box('shelf-hourglass-cap', { width: 0.16, height: 0.025, depth: 0.16 }, [xPos, yBase + 0.46, 0.45], '#7a5c3a', root, false);
      this.box('shelf-hourglass-base', { width: 0.16, height: 0.025, depth: 0.16 }, [xPos, yBase + 0.09, 0.45], '#7a5c3a', root, false);
    } else if (rowIndex === 2) {
      // 第三层:叠放的两本书
      this.box('shelf-stack-1', { width: 0.45, height: 0.05, depth: 0.32 }, [xPos, yBase + 0.07, 0.45], BOOK_COLORS[0], root);
      this.box('shelf-stack-page-1', { width: 0.43, height: 0.048, depth: 0.005 }, [xPos, yBase + 0.07, 0.61], '#fff5da', root, false);
      this.box('shelf-stack-2', { width: 0.42, height: 0.05, depth: 0.3 }, [xPos + 0.01, yBase + 0.12, 0.45], BOOK_COLORS[3], root);
      this.box('shelf-stack-page-2', { width: 0.4, height: 0.048, depth: 0.005 }, [xPos + 0.01, yBase + 0.12, 0.6], '#fff5da', root, false);
    } else {
      // 第四层:小盆栽
      this.plant(root, xPos, 0.45, 0.45);
    }
  }

  // 在书架的某层某列添加一本书(可直立或斜放)
  addShelfBook(root, region, area, book, x, yBase, leaning = false) {
    const width = 0.36 + (book.id % 3) * 0.04; // 0.36 ~ 0.44
    const height = 0.6 + (book.id % 4) * 0.05; // 0.6 ~ 0.75
    const depth = 0.4;
    const color = BOOK_COLORS[book.id % BOOK_COLORS.length];
    const mesh = this.box(`book-${book.id}`, { width, height, depth }, [x, yBase + height / 2 + 0.08, 0.1], color, root);
    mesh.metadata = { areaId: area.id, book };
    // 书脊顶/底金边
    this.box('book-spine-band-top', { width: width + 0.005, height: 0.04, depth: depth + 0.005 }, [0, height / 2 - 0.04, 0], '#dcc88a', mesh, false);
    this.box('book-spine-band-bot', { width: width + 0.005, height: 0.04, depth: depth + 0.005 }, [0, -height / 2 + 0.04, 0], '#dcc88a', mesh, false);
    // 书脊上的标题凹刻(两条)
    for (let line = 0; line < 3; line += 1) {
      const isTitle = line === 1;
      this.box(`spine-line-${line}`, { width: width * (isTitle ? 0.6 : 0.5), height: 0.02, depth: 0.008 }, [0, height * 0.2 - line * 0.12, -depth / 2 - 0.001], isTitle ? '#fff5da' : '#f3e4c7', mesh, false);
    }
    // 书页侧边(右侧露白)
    this.box('book-page-edge', { width: 0.005, height: height - 0.04, depth: depth - 0.02 }, [width / 2 - 0.003, 0, 0], '#fff5da', mesh, false);
    this.box('book-page-edge-bottom', { width: 0.005, height: 0.005, depth: depth - 0.02 }, [width / 2 - 0.003, -height / 2 + 0.005, 0], '#e8d8b0', mesh, false);
    if (leaning) {
      mesh.rotation.z = (book.id % 2 ? 1 : -1) * 0.15;
      mesh.position.x += (book.id % 2 ? 1 : -1) * 0.08;
    }
    region.bookMeshes.push(mesh);
  }

  setEditing(editing) {
    this.editing = editing;
    for (const region of this.regions.values()) region.drag.enabled = editing;
    if (editing) this.focus(null);
    this.canvas.style.cursor = editing ? 'grab' : 'default';
  }

  focus(id) {
    this.activeId = id;
    const region = this.regions.get(id);
    this.destination = region
      ? { target: region.root.position.add(new Vector3(0, 1.45, 0)), radius: 6.5, alpha: -Math.PI / 2, beta: 1.27 }
      : { ...this.overview };
  }

  focusThinker() {
    if (!this.thinker) return;
    this.activeId = null;
    this.destination = {
      target: this.thinker.root.position.add(new Vector3(0, 0.5, 0)),
      radius: 4.8,
      alpha: -Math.PI / 2,
      beta: 1.2,
    };
  }

  zoom(direction) {
    this.destination = { ...this.destination, radius: Math.max(4.5, Math.min(90, this.destination.radius * (direction > 0 ? 0.85 : 1.18))) };
  }

  // 用户从 UI 切到「平移模式」时调用:左键由「旋转」换成「平移」,
  // 再按一次切回「左键旋转、右键平移」的标准 3D 操作。
  setPanMode(enabled) {
    this.panMode = Boolean(enabled);
    if (this.panMode) {
      this.pointersInput.panningMouseButton = 0; // 左键 = 平移
      this.camera.angularSensibilityX = 0;       // 旋转灵敏度 0 = 停转
      this.camera.angularSensibilityY = 0;
    } else {
      this.pointersInput.panningMouseButton = 2; // 恢复:右键 = 平移
      this.camera.angularSensibilityX = 800;
      this.camera.angularSensibilityY = 800;
    }
  }

  clearHover() {
    if (this.hovered && !this.hovered.isDisposed()) this.hovered.position.z = 0;
    this.hovered = null;
    this.callbacks.onHover(null);
  }

  onPointer(info) {
    if (this.editing || this.dragging) return;
    let mesh = info.pickInfo?.pickedMesh;
    // Thinker click — walk up the parent chain to find the marker
    let thinkerMarker = null;
    let walk = mesh;
    while (walk && !walk.metadata?.areaId && !walk.metadata?.thinker) walk = walk.parent;
    const data = walk?.metadata;
    if (info.type === PointerEventTypes.POINTERMOVE) {
      if (this.hovered !== mesh) this.clearHover();
      if (data?.book) {
        this.hovered = mesh;
        const rect = this.canvas.getBoundingClientRect();
        this.callbacks.onHover({ book: data.book, x: info.event.clientX - rect.left, y: info.event.clientY - rect.top, type: 'book' });
      } else if (data?.thinker) {
        this.callbacks.onHover({ type: 'thinker', x: info.event.clientX - rect.left, y: info.event.clientY - rect.top });
      }
      this.canvas.style.cursor = data ? 'pointer' : 'default';
    }
    if (info.type === PointerEventTypes.POINTERTAP && data) {
      if (data.thinker) {
        this.focusThinker();
        this.callbacks.onThinker?.();
      } else if (data.book && this.activeId === data.areaId) {
        this.callbacks.onRead(data.book);
      } else if (data.areaId) {
        this.focus(data.areaId);
        this.callbacks.onOpen(data.areaId);
      }
    }
  }

  setRunning(running) {
    this.engine.stopRenderLoop(this.renderFrame);
    if (running) this.engine.runRenderLoop(this.renderFrame);
  }

  disposeRegion(region) {
    this.shadows.removeShadowCaster(region.root, true);
    region.root.dispose(false, false);
    region.owned.forEach((resource) => resource.dispose());
  }

  dispose() {
    this._teardownCameraListeners?.();
    if (this._suppressContextMenu) this.canvas.removeEventListener('contextmenu', this._suppressContextMenu);
    document.removeEventListener('visibilitychange', this.visibilityHandler);
    this.resizeObserver.disconnect();
    this.intersectionObserver.disconnect();
    this.engine.stopRenderLoop();
    this.scene.dispose();
    this.engine.dispose();
  }
}

const LibrarySceneCanvas = forwardRef(function LibrarySceneCanvas({ areas, booksByArea, activeId, editing, panMode, onOpen, onRead, onMove, onHover, onThinker, onError }, ref) {
  const canvasRef = useRef(null);
  const rendererRef = useRef(null);
  const callbacksRef = useRef({ onOpen, onRead, onMove, onHover, onThinker });
  callbacksRef.current = { onOpen, onRead, onMove, onHover, onThinker };
  useImperativeHandle(ref, () => ({
    zoom: (direction) => rendererRef.current?.zoom(direction),
    reset: () => rendererRef.current?.focus(null),
    setPanMode: (enabled) => rendererRef.current?.setPanMode(enabled),
  }), []);

  useEffect(() => {
    let renderer;
    try {
      renderer = new LibraryRenderer(canvasRef.current, {
        onOpen: (...args) => callbacksRef.current.onOpen(...args),
        onRead: (...args) => callbacksRef.current.onRead(...args),
        onMove: (...args) => callbacksRef.current.onMove(...args),
        onHover: (...args) => callbacksRef.current.onHover(...args),
        onThinker: () => callbacksRef.current.onThinker?.(),
      });
      rendererRef.current = renderer;
    } catch (err) { onError(err.message); }
    return () => { rendererRef.current = null; renderer?.dispose(); };
  }, [onError]);
  useEffect(() => { rendererRef.current?.setAreas(areas, booksByArea); }, [areas, booksByArea]);
  useEffect(() => { rendererRef.current?.setEditing(editing); }, [editing]);
  useEffect(() => { rendererRef.current?.focus(activeId); }, [activeId]);
  useEffect(() => { rendererRef.current?.setPanMode(panMode); }, [panMode]);

  return <canvas ref={canvasRef} className="library-scene-canvas" aria-label="三维图书馆；也可使用区域按钮和书架列表操作" />;
});

export default LibrarySceneCanvas;
