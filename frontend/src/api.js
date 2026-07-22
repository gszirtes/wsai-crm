import axios from "axios";

const BASE = process.env.REACT_APP_BACKEND_URL;

const api = axios.create({
  baseURL: `${BASE}/api`,
  withCredentials: true,
});

export function formatApiError(detail) {
  // null when there's nothing to format (e.g. a network-level failure with
  // no response body at all) -- every caller chains `|| e.message` after
  // this, so returning a truthy generic string here would permanently mask
  // the real error (a network/CORS failure's genuinely useful e.message,
  // like "Network Error") and it would never be shown or logged.
  if (detail == null) return null;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e)))
      .filter(Boolean)
      .join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export default api;
