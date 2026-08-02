import { motion, useReducedMotion } from 'motion/react'

/** Shared by the calibration dial and any gauge. 2px tapered needle with a
 * 4px counterweight tail, rotating about (cx, cy). The only element in the
 * app permitted a settling oscillation — one small overshoot, critically
 * damped — because that's what a real needle does. */
export function Needle({
  cx,
  cy,
  length,
  angleDeg,
  color = 'var(--phosphor)',
  animate = true,
}: {
  cx: number
  cy: number
  length: number
  /** 0° = up; positive clockwise */
  angleDeg: number
  color?: string
  animate?: boolean
}) {
  const reduced = useReducedMotion()
  const restAngle = angleDeg
  return (
    <motion.g
      initial={animate && !reduced ? { rotate: -132 } : { rotate: restAngle }}
      animate={{ rotate: restAngle }}
      transition={
        animate && !reduced
          ? { type: 'spring', stiffness: 60, damping: 11, mass: 1.1 } // ~900ms, one overshoot
          : { duration: 0 }
      }
      style={{ transformOrigin: `${cx}px ${cy}px`, transformBox: 'view-box' }}
    >
      {/* tapered blade */}
      <path
        d={`M ${cx - 1} ${cy} L ${cx} ${cy - length} L ${cx + 1} ${cy} Z`}
        fill={color}
      />
      {/* counterweight tail */}
      <rect x={cx - 2} y={cy} width={4} height={length * 0.22} rx={1} fill={color} />
    </motion.g>
  )
}
