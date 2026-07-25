import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Github, Linkedin } from "lucide-react";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LanguageToggle } from "@/components/LanguageToggle";
import { SiteNav } from "@/components/SiteNav";
import { useLanguage } from "@/contexts/LanguageContext";

interface PageLayoutProps {
  children: ReactNode;
  /** Extra controls rendered next to the language/theme toggles (e.g. the board's pause button). */
  headerActions?: ReactNode;
  /** The flight board needs more horizontal room for its table than the dashboard pages do. */
  width?: "default" | "wide";
  /** Set false on pages that render their own footer or need the full viewport. */
  showFooter?: boolean;
}

const SiteFooter = () => (
  <div className="mt-10 pb-8 text-center text-xs text-muted-foreground">
    <div className="flex flex-col items-center gap-1" dir="ltr">
      <span className="inline-flex items-center gap-1">
        <Github className="h-3.5 w-3.5" aria-hidden="true" />
        <span>GitHub:</span>{" "}
        <a
          href="https://github.com/Daniel1Maymon/israel-flights-etl"
          className="underline underline-offset-2 hover:text-foreground"
          target="_blank"
          rel="noreferrer"
        >
          israel-flights-etl
        </a>
      </span>
      <span className="inline-flex items-center gap-1">
        <Linkedin className="h-3.5 w-3.5" aria-hidden="true" />
        <span>LinkedIn:</span>{" "}
        <a
          href="https://www.linkedin.com/in/daniel-maymon/"
          className="underline underline-offset-2 hover:text-foreground"
          target="_blank"
          rel="noreferrer"
        >
          daniel-maymon
        </a>
      </span>
      <span>Data source: data.gov.il</span>
    </div>
  </div>
);

/**
 * Shared chrome for every public page: header, sticky primary nav, footer.
 *
 * Before this existed the header and the credits block were copy-pasted per page and had already
 * drifted apart (the dashboard carried a mobile-only duplicate of the flight-board button that the
 * board itself did not have). Keep new pages going through here.
 */
export const PageLayout = ({
  children,
  headerActions,
  width = "default",
  showFooter = true,
}: PageLayoutProps) => {
  const { t, isRTL } = useLanguage();

  return (
    <div className="min-h-screen bg-background" dir={isRTL ? "rtl" : "ltr"}>
      <div
        className={`container mx-auto px-4 ${
          width === "wide" ? "max-w-[1400px]" : "max-w-7xl"
        }`}
      >
        {/* Header */}
        <div className="py-4">
          <div className="flex items-center justify-between">
            <Link to="/" className="flex items-center gap-2" aria-label="RankAir">
              <img src="/favicon.png" alt="" className="h-10 w-10 rounded-xl" />
              <span className="text-2xl font-bold text-foreground">
                <span className="sm:hidden">RankAir</span>
                <span className="hidden sm:inline">{t("dashboard.title")}</span>
              </span>
            </Link>
            <div className="flex items-center gap-2">
              {headerActions}
              <LanguageToggle />
              <ThemeToggle />
            </div>
          </div>
        </div>

        <SiteNav />

        {children}

        {showFooter && <SiteFooter />}
      </div>
    </div>
  );
};
