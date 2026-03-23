export const DATA_BASE_URL = import.meta.env.VITE_DATA_URL
  || (import.meta.env.DEV
    ? '/data'
    : 'https://raw.githubusercontent.com/Yksman/perpetual_predict/data');
