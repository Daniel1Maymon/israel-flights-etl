import { Plane } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/contexts/LanguageContext";

interface DatabaseToggleProps {
  isDatabaseMode: boolean;
  onToggle: () => void;
}

export const DatabaseToggle = ({ onToggle }: DatabaseToggleProps) => {
  const { t } = useLanguage();

  return (
    <Button
      variant="outline"
      size="sm"
      onClick={onToggle}
      className="flex items-center gap-2"
    >
      <Plane className="h-4 w-4" />
      {t('board.liveBoard')}
    </Button>
  );
};
