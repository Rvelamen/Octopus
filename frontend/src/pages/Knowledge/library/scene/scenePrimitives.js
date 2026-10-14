import { Vector3 } from '@babylonjs/core/Maths/math.vector';
import { CreateBox } from '@babylonjs/core/Meshes/Builders/boxBuilder';
import { CreateSphere } from '@babylonjs/core/Meshes/Builders/sphereBuilder';

export const STONE = { light: '#c2b294', mid: '#a89a82', dark: '#7e7058', shadow: '#5d5240' };
export const WOOD = { oak: '#caa17a', walnut: '#9c6f44', cherry: '#bd8a5e', ebony: '#5d4126' };
export const BOOK_COLORS = ['#c27e69', '#7e9e92', '#8ca9be', '#d0b477', '#af92af', '#708e9b', '#c9947d', '#8a8265', '#b08a6e'];

export function sceneBox(scene, material, name, dimensions, position, color, parent = null) {
  const mesh = CreateBox(name, dimensions, scene);
  mesh.position = new Vector3(...position); mesh.material = material(color); mesh.parent = parent;
  mesh.receiveShadows = true;
  return mesh;
}

export function sceneSphere(scene, material, name, diameter, position, color, parent = null, scale = [1, 1, 1]) {
  const mesh = CreateSphere(name, { diameter, segments: 8 }, scene);
  mesh.position = new Vector3(...position); mesh.scaling = new Vector3(...scale);
  mesh.material = material(color); mesh.parent = parent;
  return mesh;
}
