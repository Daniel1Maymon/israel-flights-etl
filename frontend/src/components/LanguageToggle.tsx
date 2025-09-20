import { Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/contexts/LanguageContext";

export const LanguageToggle = () => {
  const { language, setLanguage, t } = useLanguage();

  return (
    <Button
      variant="outline"
      size="icon"
      onClick={() => setLanguage(language === "en" ? "he" : "en")}
      className="h-10 w-10 bg-background/50 border-border/50 hover:bg-muted/50"
      title={t('language.toggle')}
    >
      <Globe className="h-4 w-4" />
      <span className="sr-only">{t('language.toggle')}</span>
    </Button>
  );
};

