// Lines matching one of these keywords need a per-car-model mapping (a line can
// build several car models, each shown as a different 3D object). Every other
// line (Chassis, Engine, ...) uses a single object regardless of car model.
const MULTI_MODEL_KEYWORDS = ['final', 'trim', 'ub', 'underbody'];

function normalizeLineName(name) {
  return (name || '').toLowerCase().replace(/[^a-z0-9]/g, '');
}

export function lineNeedsCarModel(lineName) {
  const n = normalizeLineName(lineName);
  return MULTI_MODEL_KEYWORDS.some(k => n.includes(k));
}
