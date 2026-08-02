/** The second (and last) 3D moment — docs/04, docs/09.
 *
 * Orthographic camera so equal distances mean equal quantities. Orbit only,
 * no auto-rotate. Gated-out vehicles are wireframe ghosts in place. The 2D
 * table rendered beneath this (same ScatterDatum array) is the accessible
 * source of truth. prefers-reduced-motion gets a static isometric render.
 */

import { OrbitControls, Html } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { Component, useMemo, useState, type ReactNode } from 'react'
import * as THREE from 'three'
import { CUBE, position, radius, type ScatterDatum } from './scatter'

function cssVar(name: string): string {
  // colours come from the token layer only (docs/09); the named-colour
  // fallback exists for tests without a stylesheet and stays out of the
  // no-hex fence on purpose
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || 'gray'
}

const AXES: {
  label: string
  at: [number, number, number]
}[] = [
  { label: 'RISK σ% →', at: [CUBE + 0.35, -CUBE, -CUBE] },
  // mid-height on the vertical edge: the corner itself projects outside the
  // canvas at the default isometric framing
  { label: 'NET RETURN %/yr ↑', at: [-CUBE, CUBE * 0.55, -CUBE] },
  { label: 'DAYS TO CASH (log) →', at: [-CUBE, -CUBE, CUBE + 0.55] },
]

function Points({ data }: { data: ScatterDatum[] }) {
  const [hover, setHover] = useState<string | null>(null)
  const colors = useMemo(
    () => ({
      phosphor: cssVar('--phosphor'),
      brass: cssVar('--brass'),
      tertiary: cssVar('--text-tertiary'),
      rule: cssVar('--rule'),
      text: cssVar('--text-primary'),
      panel: cssVar('--panel'),
    }),
    [],
  )
  const total = data.reduce((s, d) => s + d.allocatedPaise, 0)
  const edges = useMemo(
    () =>
      new THREE.EdgesGeometry(new THREE.BoxGeometry(2 * CUBE, 2 * CUBE, 2 * CUBE)),
    [],
  )
  return (
    <>
      <lineSegments geometry={edges}>
        <lineBasicMaterial color={colors.rule} />
      </lineSegments>
      {AXES.map((a) => (
        <Html key={a.label} position={a.at} center style={{ pointerEvents: 'none' }}>
          <span
            className="legend-strip"
            style={{ color: colors.tertiary, whiteSpace: 'nowrap' }}
          >
            {a.label}
          </span>
        </Html>
      ))}
      {data.map((d) => {
        const p = position(d)
        const r = radius(d, total)
        const allocated = !d.gated && d.allocatedPaise > 0
        return (
          <mesh
            key={d.vehicle_id}
            position={p}
            onPointerOver={() => setHover(d.vehicle_id)}
            onPointerOut={() => setHover((h) => (h === d.vehicle_id ? null : h))}
          >
            <sphereGeometry args={[r, d.gated ? 10 : 24, d.gated ? 8 : 16]} />
            {d.gated ? (
              <meshBasicMaterial color={colors.tertiary} wireframe />
            ) : (
              <meshStandardMaterial
                color={allocated ? colors.phosphor : colors.tertiary}
                roughness={0.35}
                metalness={0.15}
              />
            )}
            {hover === d.vehicle_id && (
              <Html
                position={[0, r + 0.12, 0]}
                center
                style={{ pointerEvents: 'none' }}
              >
                <div
                  style={{
                    font: '400 var(--t-data) var(--font-data)',
                    background: colors.panel,
                    border: `1px solid ${allocated ? colors.brass : colors.rule}`,
                    borderRadius: 4,
                    padding: '4px 8px',
                    whiteSpace: 'nowrap',
                    color: colors.text,
                  }}
                >
                  {d.label} · σ{d.risk}% · {d.ret}%/yr · {Math.round(d.daysToCash)}d
                  {d.gated ? ` · GATED: ${d.gate}` : ''}
                </div>
              </Html>
            )}
          </mesh>
        )
      })}
    </>
  )
}

class CanvasBoundary extends Component<
  { fallback: ReactNode; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false }
  static getDerivedStateFromError() {
    return { failed: true }
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children
  }
}

export function Scatter3D({ data }: { data: ScatterDatum[] }) {
  const reduced = useMemo(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    [],
  )
  return (
    <CanvasBoundary
      fallback={
        <p style={{ color: 'var(--text-secondary)' }}>
          WebGL is unavailable; the table below is the same data.
        </p>
      }
    >
      <div style={{ height: 420 }} aria-hidden="true">
        <Canvas
          orthographic
          frameloop={reduced ? 'demand' : 'always'}
          camera={{ position: [5.2, 3.6, 6.4], zoom: 74, near: 0.1, far: 100 }}
        >
          <ambientLight intensity={0.9} />
          <directionalLight position={[4, 6, 5]} intensity={1.1} />
          <Points data={data} />
          {!reduced && (
            <OrbitControls
              enablePan={false}
              autoRotate={false}
              minZoom={40}
              maxZoom={200}
            />
          )}
        </Canvas>
      </div>
    </CanvasBoundary>
  )
}
