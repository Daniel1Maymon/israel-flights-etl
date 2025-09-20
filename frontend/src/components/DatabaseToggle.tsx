import { Database } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/contexts/LanguageContext";

interface DatabaseToggleProps {
  isDatabaseMode: boolean;
  onToggle: () => void;
}

export const DatabaseToggle = ({ isDatabaseMode, onToggle }: DatabaseToggleProps) => {
  const { t } = useLanguage();

  return (
    <Button
      variant={isDatabaseMode ? "default" : "outline"}
      size="sm"
      onClick={onToggle}
      className="flex items-center gap-2"
    >
      <Database className="h-4 w-4" />
      {isDatabaseMode ? t('database.disconnect') : t('database.connect')}
    </Button>
  );
};
