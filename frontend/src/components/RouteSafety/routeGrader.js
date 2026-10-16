import L from 'leaflet'
const ROUTE_CORRIDOR_M = 400
const ROUTE_EDGE_WEIGHT = 0.5
const ROUTE_HALF_LIFE_D = 14

const SEVERITY_TIERS = [
  {
    re: /identity theft|fraud|stolen plate|stolen license|recover|cyber|medical|welfare|alarm|assist|lost|info|check|death investigation/,
    pts: 0,
    cap: 0
  },
  {
    re: /homicide|murder|shoot|shots|stab|assault|battery|robbery|carjack|kidnap|weapon|armed|deadly missile|sexual/,
    pts: 10,
    cap: Infinity
  },
  {
    re: /harass|stalk|indecent|exposure|traffic|crash|hit and run/,
    pts: 5,
    cap: 20
  },
  { re: /theft|burglary|larceny|stolen/, pts: 2, cap: 15 },
  { re: /animal|livestock/, pts: 3, cap: 10 },
  {
    re: /domestic|fight|drug|narcotic|dui|reckless|vandal|mischief|suspicious|trespass|bomb/,
    pts: 2,
    cap: 15
  },
  // Plain disturbances are ~40% of all calls (mostly noise/neighbor disputes),
  // so they get their own small budget instead of filling the tier above
  { re: /disturbance/, pts: 1, cap: 10 }
]
const SEVERITY_DEFAULT = { pts: 1, cap: 10 }

const tierOf = (nature) => {
  const n = (nature || '').toLowerCase()
  return SEVERITY_TIERS.find((t) => t.re.test(n)) || SEVERITY_DEFAULT
}

function distToSegmentM(p, a, b) {
  const mLat = 111320
  const mLng = 111320 * Math.cos((p.lat * Math.PI) / 180)
  const ax = (a.lng - p.lng) * mLng,
    ay = (a.lat - p.lat) * mLat
  const bx = (b.lng - p.lng) * mLng,
    by = (b.lat - p.lat) * mLat
  const dx = bx - ax,
    dy = by - ay
  const len2 = dx * dx + dy * dy
  const t =
    len2 === 0 ? 0 : Math.max(0, Math.min(1, -(ax * dx + ay * dy) / len2))
  return Math.hypot(ax + t * dx, ay + t * dy)
}

function distToRouteM(p, pts) {
  let best = Infinity
  for (let i = 1; i < pts.length; i++)
    best = Math.min(best, distToSegmentM(p, pts[i - 1], pts[i]))
  return best
}

export function routeLengthKm(pts) {
  let m = 0
  for (let i = 1; i < pts.length; i++)
    m += L.latLng(pts[i - 1]).distanceTo(L.latLng(pts[i]))
  return m / 1000
}

export const scoreColor = (s) =>
  s >= 80 ? '#27ae60' : s >= 60 ? '#d9a441' : s >= 40 ? '#e67e22' : '#e74c3c'
export const scoreLabel = (s) =>
  s >= 80
    ? 'Low risk'
    : s >= 60
      ? 'Moderate risk'
      : s >= 40
        ? 'Elevated risk'
        : 'High risk'

export function gradeRoute(points, incidents, now = Date.now()) {
  if (points.length < 2) return null
  const contributors = []
  const tierTotals = new Map()

  for (const inc of incidents) {
    if (inc.lat == null || inc.lon == null) continue
    const p = { lat: inc.lat, lng: inc.lon }
    const d = distToRouteM(p, points)
    if (d > ROUTE_CORRIDOR_M) continue

    const tier = tierOf(inc.nature)
    const t = new Date(inc.occurred_at).getTime()
    const ageDays = Number.isNaN(t) ? 0 : Math.max(0, (now - t) / 86400000)
    const pts =
      tier.pts *
      Math.pow(0.5, ageDays / ROUTE_HALF_LIFE_D) *
      (1 - (1 - ROUTE_EDGE_WEIGHT) * (d / ROUTE_CORRIDOR_M))

    tierTotals.set(tier, (tierTotals.get(tier) || 0) + pts)
    contributors.push({ inc, pts, d })
  }

  let penalty = 0
  for (const [tier, total] of tierTotals) penalty += Math.min(total, tier.cap)

  contributors.sort((a, b) => b.pts - a.pts)
  return {
    score: Math.max(0, Math.round(100 - penalty)),
    contributors,
    km: routeLengthKm(points)
  }
}
