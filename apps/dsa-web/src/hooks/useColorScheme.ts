import { useEffect, useState } from 'react';
import { systemConfigApi } from '../api/systemConfig';

type ColorScheme = 'green_up' | 'red_up';

/**
 * Reads the MARKET_REVIEW_COLOR_SCHEME system config and returns
 * helper functions for applying rise/fall CSS classes.
 *
 * - green_up (default): gains → text-success (green), losses → text-danger (red)
 * - red_up:            gains → text-danger (red),   losses → text-success (green)
 */
export function useColorScheme() {
  const [scheme, setScheme] = useState<ColorScheme>('green_up');

  useEffect(() => {
    let active = true;

    void systemConfigApi.getConfig(false)
      .then((config) => {
        if (!active) return;
        const item = config.items.find((i) => i.key === 'MARKET_REVIEW_COLOR_SCHEME');
        const value = String(item?.value ?? '').trim().toLowerCase();
        if (value === 'red_up') {
          setScheme('red_up');
        }
      })
      .catch(() => {
        // Fail silently — default green_up is a safe fallback
      });

    return () => { active = false; };
  }, []);

  const riseClass = scheme === 'red_up' ? 'text-danger' : 'text-success';
  const fallClass = scheme === 'red_up' ? 'text-success' : 'text-danger';

  return { scheme, riseClass, fallClass };
}
