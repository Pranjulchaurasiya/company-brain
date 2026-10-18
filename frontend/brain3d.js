/**
 * Company Brain 3D Animated Graph Visualizer
 * Built with Three.js for clean, elegant, interactive 3D spatial node exploration.
 */

class CompanyBrain3D {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    if (!this.container) {
      console.error(`Container #${containerId} not found`);
      return;
    }

    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.controls = null;
    this.raycaster = new THREE.Raycaster();
    this.mouse = new THREE.Vector2();
    
    this.nodeMeshes = [];
    this.edgeLines = [];
    this.pulseParticles = [];
    this.nodeMap = new Map();
    this.graphData = { nodes: [], edges: [] };

    this.isAutoRotating = true;
    this.hoveredNode = null;
    this.selectedNode = null;
    this.activeFilter = 'all';

    // Palette: Clean, professional, elegant (non-neon)
    this.palette = {
      Employee: 0x4338ca,   // Royal Indigo
      Project: 0x0284c7,    // Sky Blue
      Service: 0x0891b2,    // Cyan
      Task: 0x7c3aed,       // Purple
      Decision: 0xc026d3,   // Fuchsia
      Fact: 0x059669,       // Emerald
      Source: 0xd97706,     // Warm Amber
      Evidence: 0xe11d48,   // Coral Rose
      Deliverable: 0x0d9488,// Teal
      Ticket: 0xe11d48,     // Crimson
      Skill: 0x64748b,      // Slate
      Team: 0x2563eb,       // Blue
      Goal: 0x4f46e5,       // Indigo
      Memory: 0x10b981,     // Green
      ChatMessage: 0x94a3b8,// Muted Slate
      AgentMessage: 0x6366f1,// Indigo
      Default: 0x64748b     // Neutral
    };

    this.init();
  }

  init() {
    const width = this.container.clientWidth || 600;
    const height = this.container.clientHeight || 450;

    // 1. Scene
    this.scene = new THREE.Scene();
    
    // 2. Camera
    this.camera = new THREE.PerspectiveCamera(45, width / height, 1, 3000);
    this.camera.position.set(0, 70, 360);

    // 3. Renderer (Clean & transparent with antialiasing)
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = false;
    this.container.innerHTML = '';
    this.container.appendChild(this.renderer.domElement);

    // 4. Lights (Soft, balanced, non-glaring)
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.85);
    this.scene.add(ambientLight);

    const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.7);
    dirLight1.position.set(100, 150, 120);
    this.scene.add(dirLight1);

    const dirLight2 = new THREE.DirectionalLight(0xe0e7ff, 0.4);
    dirLight2.position.set(-100, -100, -100);
    this.scene.add(dirLight2);

    // 5. Controls
    if (typeof THREE.OrbitControls !== 'undefined') {
      this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
      this.controls.enableDamping = true;
      this.controls.dampingFactor = 0.06;
      this.controls.minDistance = 60;
      this.controls.maxDistance = 750;
      this.controls.maxPolarAngle = Math.PI - 0.1;
      this.controls.autoRotate = this.isAutoRotating;
      this.controls.autoRotateSpeed = 0.8;
    }

    // 6. Subtle Orbital Guide Ring
    const ringGeo = new THREE.RingGeometry(178, 180, 64);
    const ringMat = new THREE.MeshBasicMaterial({ 
      color: 0x94a3b8, 
      side: THREE.DoubleSide, 
      transparent: true, 
      opacity: 0.15 
    });
    const ringMesh = new THREE.Mesh(ringGeo, ringMat);
    ringMesh.rotation.x = Math.PI / 2;
    this.scene.add(ringMesh);

    // 7. Auto-fit and Resize Handling
    if (window.ResizeObserver) {
      this.resizeObserver = new ResizeObserver(() => this.handleResize());
      this.resizeObserver.observe(this.container);
    }
    window.addEventListener('resize', () => this.handleResize());

    // 7. Event listeners
    window.addEventListener('resize', () => this.onResize());
    this.renderer.domElement.addEventListener('mousemove', (e) => this.onMouseMove(e));
    this.renderer.domElement.addEventListener('click', (e) => this.onClick(e));

    // 8. Start Loop
    this.animate();
  }

  setData(data) {
    this.graphData = data || { nodes: [], edges: [] };
    this.rebuildGraph();
  }

  rebuildGraph() {
    // Clear previous elements
    this.nodeMeshes.forEach(mesh => {
      this.scene.remove(mesh);
      if (mesh.geometry) mesh.geometry.dispose();
      if (mesh.material) mesh.material.dispose();
    });
    this.edgeLines.forEach(line => {
      this.scene.remove(line);
      if (line.geometry) line.geometry.dispose();
      if (line.material) line.material.dispose();
    });
    this.pulseParticles.forEach(p => {
      this.scene.remove(p.mesh);
      if (p.mesh.geometry) p.mesh.geometry.dispose();
    });

    this.nodeMeshes = [];
    this.edgeLines = [];
    this.pulseParticles = [];
    this.nodeMap.clear();

    const nodes = this.graphData.nodes || [];
    const edges = this.graphData.edges || [];

    if (nodes.length === 0) return;

    // Filter secondary noise if needed (e.g. keep core nodes prominently visible)
    const primaryTypes = new Set(['Employee', 'Team', 'Project', 'Service', 'Goal', 'Task', 'Decision', 'Fact', 'Ticket', 'Evidence', 'Source', 'Deliverable']);

    // Categorized 3D Shell Layout:
    // Core Employees & Goals at inner sphere
    // Projects & Services in middle layer
    // Decisions, Facts, Tasks in operational ring
    // Evidence, Sources in outer verification ring
    const total = nodes.length;
    nodes.forEach((node, i) => {
      let r = 110;
      let yBias = 0;
      let sphereRadius = 4.5;

      if (node.type === 'Employee') {
        r = 65;
        sphereRadius = 8.5;
        yBias = (i % 2 === 0 ? 20 : -20);
      } else if (node.type === 'Project' || node.type === 'Service') {
        r = 95;
        sphereRadius = 7.0;
      } else if (node.type === 'Goal' || node.type === 'Deliverable') {
        r = 50;
        sphereRadius = 9.0;
        yBias = 30;
      } else if (node.type === 'Decision' || node.type === 'Fact') {
        r = 135;
        sphereRadius = 5.5;
      } else if (node.type === 'Evidence' || node.type === 'Source') {
        r = 165;
        sphereRadius = 4.2;
      } else {
        r = 120 + (i % 40);
        sphereRadius = 3.5;
      }

      // Golden spiral distribution on sphere surface
      const phi = Math.acos(-1 + (2 * i) / total);
      const theta = Math.sqrt(total * Math.PI) * phi;

      const x = r * Math.sin(phi) * Math.cos(theta);
      const y = (r * Math.cos(phi)) * 0.65 + yBias;
      const z = r * Math.sin(phi) * Math.sin(theta);

      // Create Node Mesh (Soft ceramic gloss standard material)
      const colorHex = this.palette[node.type] || this.palette.Default;
      const geometry = new THREE.SphereGeometry(sphereRadius, 24, 24);
      const material = new THREE.MeshStandardMaterial({
        color: colorHex,
        roughness: 0.35,
        metalness: 0.15,
        emissive: colorHex,
        emissiveIntensity: 0.18
      });

      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.set(x, y, z);
      mesh.userData = {
        node: node,
        baseColor: colorHex,
        baseScale: 1.0,
        originalPosition: new THREE.Vector3(x, y, z)
      };

      this.scene.add(mesh);
      this.nodeMeshes.push(mesh);
      this.nodeMap.set(node.id, mesh);
    });

    // Create Edges
    const lineMat = new THREE.LineBasicMaterial({
      color: 0x94a3b8,
      transparent: true,
      opacity: 0.22,
      linewidth: 1
    });

    const linePositions = [];
    const connectedEdges = [];

    edges.forEach(edge => {
      const srcMesh = this.nodeMap.get(edge.source);
      const tgtMesh = this.nodeMap.get(edge.target);

      if (srcMesh && tgtMesh) {
        linePositions.push(
          srcMesh.position.x, srcMesh.position.y, srcMesh.position.z,
          tgtMesh.position.x, tgtMesh.position.y, tgtMesh.position.z
        );
        connectedEdges.push({ src: srcMesh, tgt: tgtMesh, type: edge.type });
      }
    });

    if (linePositions.length > 0) {
      const lineGeo = new THREE.BufferGeometry();
      lineGeo.setAttribute('position', new THREE.Float32BufferAttribute(linePositions, 3));
      const lineMesh = new THREE.LineSegments(lineGeo, lineMat);
      this.scene.add(lineMesh);
      this.edgeLines.push(lineMesh);
    }

    // Spawn Animated Pulse Particles along active workflow edges
    const sampleEdges = connectedEdges.slice(0, Math.min(24, connectedEdges.length));
    sampleEdges.forEach((e, idx) => {
      const pGeo = new THREE.SphereGeometry(1.6, 8, 8);
      const pMat = new THREE.MeshBasicMaterial({
        color: 0x6366f1,
        transparent: true,
        opacity: 0.85
      });
      const pMesh = new THREE.Mesh(pGeo, pMat);
      pMesh.position.copy(e.src.position);
      this.scene.add(pMesh);

      this.pulseParticles.push({
        mesh: pMesh,
        src: e.src.position,
        tgt: e.tgt.position,
        progress: (idx * 0.12) % 1.0,
        speed: 0.004 + Math.random() * 0.003
      });
    });
  }

  animate() {
    requestAnimationFrame(() => this.animate());

    // Update orbit controls
    if (this.controls) {
      this.controls.autoRotate = this.isAutoRotating;
      this.controls.update();
    }

    // Animate data flow particles
    this.pulseParticles.forEach(p => {
      p.progress += p.speed;
      if (p.progress > 1.0) p.progress = 0;
      p.mesh.position.lerpVectors(p.src, p.tgt, p.progress);
    });

    this.renderer.render(this.scene, this.camera);
  }

  onResize() {
    if (!this.container || !this.renderer || !this.camera) return;
    const width = this.container.clientWidth;
    const height = this.container.clientHeight;
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(width, height);
  }

  onMouseMove(e) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.nodeMeshes);

    if (intersects.length > 0) {
      const hit = intersects[0].object;
      if (this.hoveredNode !== hit) {
        this.resetHover();
        this.hoveredNode = hit;
        this.hoveredNode.scale.set(1.4, 1.4, 1.4);
        this.hoveredNode.material.emissiveIntensity = 0.55;
        this.showTooltip(hit.userData.node, e.clientX, e.clientY);
        this.renderer.domElement.style.cursor = 'pointer';
      }
    } else {
      if (this.hoveredNode) {
        this.resetHover();
        this.hideTooltip();
        this.renderer.domElement.style.cursor = 'default';
      }
    }
  }

  resetHover() {
    if (this.hoveredNode) {
      this.hoveredNode.scale.set(1.0, 1.0, 1.0);
      this.hoveredNode.material.emissiveIntensity = 0.18;
      this.hoveredNode = null;
    }
  }

  onClick(e) {
    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersects = this.raycaster.intersectObjects(this.nodeMeshes);

    if (intersects.length > 0) {
      const hit = intersects[0].object;
      const node = hit.userData.node;
      this.focusNode(hit);

      if (window.onNode3DClick) {
        window.onNode3DClick(node);
      }
    }
  }

  focusNode(mesh) {
    if (!this.controls) return;
    const targetPos = mesh.position.clone();
    
    // Smooth camera shift toward node
    const offset = new THREE.Vector3(0, 20, 100);
    const newCamPos = targetPos.clone().add(offset);

    let t = 0;
    const startPos = this.camera.position.clone();
    const startTarget = this.controls.target.clone();

    const animateFocus = () => {
      t += 0.05;
      if (t <= 1) {
        this.camera.position.lerpVectors(startPos, newCamPos, t);
        this.controls.target.lerpVectors(startTarget, targetPos, t);
        requestAnimationFrame(animateFocus);
      }
    };
    animateFocus();
  }

  handleResize() {
    if (!this.container || !this.renderer || !this.camera) return;
    const width = this.container.clientWidth || 600;
    const height = this.container.clientHeight || 340;
    if (width > 0 && height > 0) {
      this.camera.aspect = width / height;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(width, height);
    }
  }

  zoomIn(factor = 0.8) {
    if (!this.camera || !this.controls) return;
    this.camera.position.sub(this.controls.target).multiplyScalar(factor).add(this.controls.target);
    this.controls.update();
  }

  zoomOut(factor = 1.25) {
    if (!this.camera || !this.controls) return;
    this.camera.position.sub(this.controls.target).multiplyScalar(factor).add(this.controls.target);
    this.controls.update();
  }

  fitToBounds() {
    if (!this.nodeMeshes.length || !this.controls) {
      this.resetCamera();
      return;
    }
    const box = new THREE.Box3();
    this.nodeMeshes.forEach(m => box.expandByPoint(m.position));
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z, 100);
    this.controls.target.copy(center);
    this.camera.position.set(center.x, center.y + maxDim * 0.3, center.z + maxDim * 1.4 + 40);
    this.controls.update();
  }

  resetCamera() {
    if (!this.controls) return;
    this.controls.target.set(0, 0, 0);
    this.camera.position.set(0, 70, 360);
    this.isAutoRotating = true;
    this.handleResize();
  }

  toggleAutoRotate() {
    this.isAutoRotating = !this.isAutoRotating;
    return this.isAutoRotating;
  }

  filterByType(typeGroup) {
    this.activeFilter = typeGroup;
    this.nodeMeshes.forEach(mesh => {
      const type = mesh.userData.node.type;
      let visible = true;

      if (typeGroup === 'employees') {
        visible = (type === 'Employee' || type === 'Team');
      } else if (typeGroup === 'projects') {
        visible = (type === 'Project' || type === 'Service' || type === 'Goal');
      } else if (typeGroup === 'evidence') {
        visible = (type === 'Evidence' || type === 'Source' || type === 'Fact');
      } else if (typeGroup === 'decisions') {
        visible = (type === 'Decision' || type === 'Task' || type === 'Ticket');
      }

      mesh.visible = visible;
    });
  }

  showTooltip(node, clientX, clientY) {
    let tip = document.getElementById('brain3d-tooltip');
    if (!tip) {
      tip = document.createElement('div');
      tip.id = 'brain3d-tooltip';
      tip.style.position = 'fixed';
      tip.style.zIndex = '1000';
      tip.style.pointerEvents = 'none';
      tip.style.background = '#ffffff';
      tip.style.color = '#0f172a';
      tip.style.padding = '10px 14px';
      tip.style.borderRadius = '10px';
      tip.style.boxShadow = '0 10px 25px -5px rgba(0,0,0,0.1), 0 4px 6px -2px rgba(0,0,0,0.05)';
      tip.style.border = '1px solid #e2e8f0';
      tip.style.fontFamily = "'Inter', sans-serif";
      tip.style.fontSize = '12px';
      tip.style.maxWidth = '260px';
      tip.style.lineHeight = '1.4';
      tip.style.transition = 'opacity 0.15s ease, transform 0.15s ease';
      document.body.appendChild(tip);
    }

    const title = node.label || node.id;
    const type = node.type;
    const dept = node.properties?.department || node.properties?.title || node.properties?.status || '';

    tip.innerHTML = `
      <div style="display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:4px;">
        <strong style="font-weight:600; color:#0f172a; font-size:13px;">${title}</strong>
        <span style="background:#f1f5f9; color:#475569; font-size:10px; padding:2px 6px; border-radius:4px; font-weight:600;">${type}</span>
      </div>
      ${dept ? `<div style="color:#64748b; font-size:11px; margin-bottom:4px;">${dept}</div>` : ''}
      <div style="font-size:10px; color:#94a3b8; font-family:'JetBrains Mono',monospace;">ID: ${node.id}</div>
      <div style="margin-top:6px; font-size:10px; color:#6366f1; font-weight:500;">Click node to inspect in FalkorDB &rarr;</div>
    `;

    tip.style.left = `${clientX + 14}px`;
    tip.style.top = `${clientY + 14}px`;
    tip.style.opacity = '1';
    tip.style.transform = 'translateY(0)';
  }

  hideTooltip() {
    const tip = document.getElementById('brain3d-tooltip');
    if (tip) {
      tip.style.opacity = '0';
      tip.style.transform = 'translateY(4px)';
    }
  }
}

// Global expose
window.CompanyBrain3D = CompanyBrain3D;
