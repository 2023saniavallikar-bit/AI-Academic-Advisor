import * as THREE from './vendor/three.module.js';

let disposeScene = null;
function initScene() {
  const mount = document.getElementById('heroScene');
  if (!mount) return;
  disposeScene?.();
  disposeScene = null;

  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
  } catch (error) {
    console.error('Three.js could not create a WebGL renderer; showing the static scene fallback.', error);
    mount.classList.add('scene-fallback');
  }
  if (!renderer) return;

  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.setSize(mount.clientWidth, mount.clientHeight, false);
  mount.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(36, mount.clientWidth / mount.clientHeight, 0.1, 20);
  camera.position.z = 5;

  const root = new THREE.Group();
  scene.add(root);

  const color = () => getComputedStyle(document.documentElement).getPropertyValue('--brand-text').trim() || '#5274ad';
  const wireMaterial = new THREE.MeshBasicMaterial({ color: color(), wireframe: true, transparent: true, opacity: 0.52 });
  const core = new THREE.Mesh(new THREE.IcosahedronGeometry(1.05, 2), wireMaterial);
  root.add(core);

  const ringMaterial = new THREE.MeshBasicMaterial({ color: color(), transparent: true, opacity: 0.36 });
  const ring = new THREE.Mesh(new THREE.TorusGeometry(1.38, 0.008, 8, 120), ringMaterial);
  ring.rotation.set(0.85, 0.3, -0.5);
  root.add(ring);

  const pointsGeometry = new THREE.BufferGeometry();
  const positions = new Float32Array(24 * 3);
  for (let i = 0; i < 24; i += 1) {
    const y = 1 - (i / 23) * 2;
    const radius = Math.sqrt(1 - y * y);
    const angle = Math.PI * (3 - Math.sqrt(5)) * i;
    positions[i * 3] = Math.cos(angle) * radius * 1.065;
    positions[i * 3 + 1] = y * 1.065;
    positions[i * 3 + 2] = Math.sin(angle) * radius * 1.065;
  }
  pointsGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const pointsMaterial = new THREE.PointsMaterial({ color: color(), size: 0.035, transparent: true, opacity: 0.9 });
  const points = new THREE.Points(pointsGeometry, pointsMaterial);
  root.add(points);

  const resize = new ResizeObserver(() => {
    const width = mount.clientWidth;
    const height = mount.clientHeight;
    if (!width || !height) return;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height, false);
    renderer.render(scene, camera);
  });
  resize.observe(mount);

  let frame = 0;
  let disposed = false;
  const render = () => {
    frame = 0;
    if (disposed) return;
    if (!reducedMotion.matches) {
      root.rotation.y += 0.0015;
      root.rotation.x += 0.00035;
    }
    renderer.render(scene, camera);
    if (!reducedMotion.matches) frame = window.requestAnimationFrame(render);
  };
  const updateMotion = () => {
    if (reducedMotion.matches) {
      window.cancelAnimationFrame(frame);
      frame = 0;
      renderer.render(scene, camera);
    } else if (!frame) {
      frame = window.requestAnimationFrame(render);
    }
  };
  const updateColors = () => {
    wireMaterial.color.set(color());
    ringMaterial.color.set(color());
    pointsMaterial.color.set(color());
    renderer.render(scene, camera);
  };
  const themeObserver = new MutationObserver(updateColors);
  themeObserver.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-theme'],
  });
  reducedMotion.addEventListener('change', updateMotion);
  disposeScene = () => {
    disposed = true;
    window.cancelAnimationFrame(frame);
    resize.disconnect();
    themeObserver.disconnect();
    reducedMotion.removeEventListener('change', updateMotion);
    core.geometry.dispose();
    ring.geometry.dispose();
    pointsGeometry.dispose();
    wireMaterial.dispose();
    ringMaterial.dispose();
    pointsMaterial.dispose();
    renderer.dispose();
    renderer.domElement.remove();
  };
  updateMotion();
}

document.addEventListener('vg:welcome-rendered', initScene);
initScene();
