import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

let renderer;
let scene;
let camera;
let controls;
let animationFrame;
let resizeObserver;

function disposeScene() {
  if (animationFrame) {
    cancelAnimationFrame(animationFrame);
    animationFrame = null;
  }
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  if (controls) {
    controls.dispose();
    controls = null;
  }
  if (scene) {
    scene.traverse((object) => {
      if (object.geometry) {
        object.geometry.dispose();
      }
      if (object.material) {
        if (Array.isArray(object.material)) {
          object.material.forEach((material) => material.dispose());
        } else {
          object.material.dispose();
        }
      }
    });
  }
  if (renderer) {
    renderer.dispose();
    renderer = null;
  }
}

function colorForStop(seq, maxSeq) {
  const t = maxSeq ? seq / maxSeq : 0;
  return new THREE.Color().setHSL(0.05 + (1 - t) * 0.33, 0.78, 0.52);
}

export function renderTruck(container, loadPlan) {
  disposeScene();
  container.innerHTML = "";
  const rect = container.getBoundingClientRect();
  const width = Math.max(120, Math.floor(rect.width || container.clientWidth || 150));
  const height = Math.max(180, Math.floor(rect.height || container.clientHeight || 220));
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0xf1f6f2);
  camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 100);
  camera.position.set(4.8, 3.8, 5.8);
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.domElement.style.width = "100%";
  renderer.domElement.style.height = "100%";
  renderer.domElement.style.display = "block";
  container.appendChild(renderer.domElement);
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.target.set(0.4, 0.45, 0);

  scene.add(new THREE.HemisphereLight(0xffffff, 0xb7c6b8, 2.4));
  const keyLight = new THREE.DirectionalLight(0xffffff, 1.1);
  keyLight.position.set(3, 6, 4);
  scene.add(keyLight);
  const bed = new THREE.Mesh(
    new THREE.BoxGeometry(4.8, 0.18, 2.2),
    new THREE.MeshStandardMaterial({ color: 0x2d3530, roughness: 0.7 })
  );
  bed.position.y = -0.1;
  scene.add(bed);

  const railMaterial = new THREE.MeshStandardMaterial({ color: 0x829088, roughness: 0.8 });
  [-1.2, 1.2].forEach((z) => {
    const rail = new THREE.Mesh(new THREE.BoxGeometry(4.9, 0.16, 0.08), railMaterial);
    rail.position.set(0, 0.24, z);
    scene.add(rail);
  });

  const pallets = loadPlan?.pallets || [];
  const maxSeq = Math.max(1, ...pallets.map((pallet) => pallet.first_unload_stop_seq || 1));
  pallets.forEach((pallet, index) => {
    const col = index % 2;
    const row = Math.floor(index / 2);
    const x = -1.8 + row * 1.2;
    const z = col === 0 ? -0.58 : 0.58;
    const heightScale = 0.25 + (pallet.occupation_pct || 10) / 100;
    const box = new THREE.Mesh(
      new THREE.BoxGeometry(0.95, heightScale, 0.9),
      new THREE.MeshStandardMaterial({ color: colorForStop(pallet.first_unload_stop_seq || 1, maxSeq), roughness: 0.55 })
    );
    box.position.set(x, heightScale / 2, z);
    scene.add(box);
  });

  function resize() {
    const nextRect = container.getBoundingClientRect();
    const nextWidth = Math.max(120, Math.floor(nextRect.width || 150));
    const nextHeight = Math.max(180, Math.floor(nextRect.height || 220));
    camera.aspect = nextWidth / nextHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(nextWidth, nextHeight, false);
  }

  resizeObserver = new ResizeObserver(resize);
  resizeObserver.observe(container);
  resize();

  function animate() {
    controls.update();
    renderer.render(scene, camera);
    animationFrame = requestAnimationFrame(animate);
  }
  animationFrame = requestAnimationFrame(animate);
}
