const WMO_MAP = {
  0: { icon: '☀️', text: '晴' },
  1: { icon: '🌤️', text: '晴间多云' },
  2: { icon: '⛅', text: '多云' },
  3: { icon: '☁️', text: '阴' },
  45: { icon: '🌫️', text: '雾' },
  48: { icon: '🌫️', text: '雾凇' },
  51: { icon: '🌦️', text: '小毛毛雨' },
  53: { icon: '🌦️', text: '毛毛雨' },
  55: { icon: '🌦️', text: '大毛毛雨' },
  56: { icon: '🌧️', text: '冻毛毛雨' },
  57: { icon: '🌧️', text: '冻雨' },
  61: { icon: '🌧️', text: '小雨' },
  63: { icon: '🌧️', text: '中雨' },
  65: { icon: '🌧️', text: '大雨' },
  66: { icon: '🌧️', text: '冻小雨' },
  67: { icon: '🌧️', text: '冻大雨' },
  71: { icon: '🌨️', text: '小雪' },
  73: { icon: '🌨️', text: '中雪' },
  75: { icon: '🌨️', text: '大雪' },
  77: { icon: '🌨️', text: '雪粒' },
  80: { icon: '🌧️', text: '小阵雨' },
  81: { icon: '🌧️', text: '中阵雨' },
  82: { icon: '🌧️', text: '大阵雨' },
  85: { icon: '🌨️', text: '小阵雪' },
  86: { icon: '🌨️', text: '大阵雪' },
  95: { icon: '⛈️', text: '雷暴' },
  96: { icon: '⛈️', text: '雷暴冰雹' },
  99: { icon: '⛈️', text: '强雷暴冰雹' },
};

const DEFAULT_LOCATION = {
  latitude: 22.7217,
  longitude: 114.0408,
  city: '龙华区',
  province: '深圳市',
};

function parseWMO(code) {
  return WMO_MAP[code] || { icon: '🌈', text: '未知' };
}

let _cache = null;
let _cacheTime = 0;
const CACHE_MS = 30 * 60 * 1000;

export async function getWeather() {
  if (_cache && Date.now() - _cacheTime < CACHE_MS) return _cache;

  try {
    let latitude = DEFAULT_LOCATION.latitude;
    let longitude = DEFAULT_LOCATION.longitude;
    let city = DEFAULT_LOCATION.city;
    let province = DEFAULT_LOCATION.province;

    try {
      const pos = await new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 });
      });
      latitude = pos.coords.latitude;
      longitude = pos.coords.longitude;
    } catch {
      // 获取不到地理位置时使用默认：深圳市龙华区
    }

    const url = `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}&current=temperature_2m,weather_code&daily=temperature_2m_max,temperature_2m_min,weather_code&timezone=auto&forecast_days=3`;
    const res = await fetch(url);
    const data = await res.json();

    const current = data.current;
    const wmo = parseWMO(current.weather_code);

    try {
      const cityRes = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json&accept-language=zh`);
      const cityData = await cityRes.json();
      city = cityData.address?.city || cityData.address?.county || city || DEFAULT_LOCATION.city;
      province = cityData.address?.state || province || DEFAULT_LOCATION.province;
    } catch {
      city = city || DEFAULT_LOCATION.city;
      province = province || DEFAULT_LOCATION.province;
    }

    const forecast = (data.daily?.time || []).map((t, i) => ({
      date: t,
      wmo: parseWMO(data.daily.weather_code[i]),
      max: Math.round(data.daily.temperature_2m_max[i]),
      min: Math.round(data.daily.temperature_2m_min[i]),
    }));

    _cache = {
      icon: wmo.icon,
      text: wmo.text,
      temp: Math.round(current.temperature_2m),
      city,
      province,
      forecast,
    };
    _cacheTime = Date.now();
    return _cache;
  } catch {
    return {
      icon: '🌤️',
      text: '天气获取失败',
      temp: 0,
      city: DEFAULT_LOCATION.city,
      province: DEFAULT_LOCATION.province,
      forecast: [],
    };
  }
}
