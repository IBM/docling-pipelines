/**
 * i18n message loader.
 *
 * Merges app messages with Elyra canvas bundle messages so that
 * CommonCanvas, Toolbar, Properties etc. are also localized within
 * the single root IntlProvider.
 *
 * Supported locales are enumerated in LOCALE_MESSAGES. Adding a new
 * locale only requires importing its JSON file and adding it to the map.
 *
 * Usage:
 *   import { loadMessages, DEFAULT_LOCALE } from '@/i18n';
 *   const messages = loadMessages('en');
 */

import CommonCanvasBundles from '@elyra/canvas/locales/common-canvas/locales';
import ToolbarBundles from '@elyra/canvas/locales/toolbar/locales';
import PropertiesBundles from '@elyra/canvas/locales/common-properties/locales';
import CommandActionsBundles from '@elyra/canvas/locales/command-actions/locales';
import PaletteBundles from '@elyra/canvas/locales/palette/locales';

export const DEFAULT_LOCALE = 'en';

type Messages = Record<string, string>;

/** Elyra bundle map shape: { [locale]: { [id]: string } } */
type ElyraBundle = Record<string, Record<string, string>>;

const ELYRA_BUNDLES: ElyraBundle[] = [
  CommonCanvasBundles,
  ToolbarBundles,
  PropertiesBundles,
  CommandActionsBundles,
  PaletteBundles,
];

/**
 * Merges all Elyra locale bundles for the given locale into one flat
 * message map. Falls back to English entries for any bundle that does
 * not carry a translation for the requested locale.
 */
function getElyraMessages(locale: string): Messages {
  return ELYRA_BUNDLES.reduce<Messages>((acc, bundle) => {
    const localeMessages = bundle[locale] ?? bundle[DEFAULT_LOCALE] ?? {};
    return { ...acc, ...localeMessages };
  }, {});
}

/**
 * Returns the merged message map (app strings + Elyra canvas strings)
 * for the requested locale. Dynamically imports only the required locale
 * based on the user's browser language.
 * Falls back to English if the requested locale file does not exist.
 */
export async function loadMessages(locale: string): Promise<Messages> {
  let appMessages: Messages;
  try {
    const module = await import(`./messages_${locale}.json`);
    appMessages = module.default;
  } catch {
    const fallback = await import('./messages_en.json');
    appMessages = fallback.default;
  }

  const elyraMessages = getElyraMessages(locale);
  // App messages last so they override any accidental ID collision with Elyra
  return { ...elyraMessages, ...appMessages };
}
