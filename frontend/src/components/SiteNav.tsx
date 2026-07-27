import { NavLink } from "react-router-dom";
import { BarChart3, Building2, Lightbulb, PlaneTakeoff, RotateCcw } from "lucide-react";
import { useLanguage } from "@/contexts/LanguageContext";

/**
 * Primary site navigation.
 *
 * Underline-tab style, deliberately matching the arrivals/departures tabs already used inside
 * FlightBoard so the two levels of tabs read as the same design language.
 *
 * /admin is intentionally absent — it is token-gated and unlisted.
 */
const NAV_ITEMS = [
  { to: "/", labelKey: "nav.rankings", Icon: BarChart3, end: true },
  { to: "/airlines", labelKey: "nav.airlinePerformance", Icon: Building2, end: false },
  { to: "/insights", labelKey: "nav.insights", Icon: Lightbulb, end: false },
  { to: "/recovery", labelKey: "nav.recovery", Icon: RotateCcw, end: false },
  { to: "/flight-board", labelKey: "nav.flightBoard", Icon: PlaneTakeoff, end: false },
] as const;

export const SiteNav = () => {
  const { t } = useLanguage();

  return (
    <nav
      aria-label={t("nav.primary")}
      // `sticky top-0` keeps the tabs reachable on the long scrolling pages (/insights especially).
      // The background must be opaque, not transparent, or table rows show through while scrolling.
      className="sticky top-0 z-30 -mx-4 mb-6 border-b border-border bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/80"
    >
      {/* overflow-x-auto lets the 5 tabs scroll horizontally on narrow screens rather than wrap
          into a second row, which would make the sticky bar eat the viewport on mobile.
          The centering lives on an inner w-max track, not as justify-center on the scroll
          container — that clips the leading tab once the tabs are wider than the viewport. */}
      <div className="overflow-x-auto scrollbar-none">
        <div className="mx-auto flex w-max gap-1">
          {NAV_ITEMS.map(({ to, labelKey, Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-3.5 text-[15px] font-medium transition-colors -mb-px sm:gap-2 sm:px-6 sm:py-4 sm:text-base ${
                  isActive
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`
              }
            >
              {({ isActive }) => (
                // aria-current is what actually conveys "you are here" to a screen reader; the
                // colour change alone does not.
                <span
                  className="flex items-center gap-2"
                  aria-current={isActive ? "page" : undefined}
                >
                  <Icon className="h-[18px] w-[18px] sm:h-5 sm:w-5" aria-hidden="true" />
                  {t(labelKey)}
                </span>
              )}
            </NavLink>
          ))}
        </div>
      </div>
    </nav>
  );
};
