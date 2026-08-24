import imp.ImproVisor;
import imp.com.ExportToMusicXMLCommand;
import imp.data.Leadsheet;
import imp.data.Score;
import imp.data.Transposition;
import imp.data.advice.Advisor;
import imp.util.Preferences;
import java.io.File;
import java.io.FileInputStream;
import java.io.InputStream;
import polya.Polylist;
import polya.Tokenizer;

/** Headless command-line bridge from an Impro-Visor leadsheet to MusicXML. */
public final class ImproVisorBridge {
    private static final int EXIT_FAILURE = 1;
    private static final int EXIT_USAGE = 2;

    private ImproVisorBridge() {
    }

    public static void main(String[] args) {
        if (args.length != 2) {
            fail(EXIT_USAGE, "Uso: ImproVisorBridge <input.ls> <output.xml>");
        }

        if (!Boolean.parseBoolean(System.getProperty("java.awt.headless"))) {
            fail(EXIT_USAGE, "Execute com -Djava.awt.headless=true.");
        }

        File input = new File(args[0]);
        File output = new File(args[1]);

        if (!input.isFile() || !input.canRead()) {
            fail(EXIT_FAILURE, "Arquivo .ls inexistente ou ilegivel.");
        }

        try {
            Preferences.loadPreferences();
            loadVocabulary();
            Advisor.readStyles();
            Score score = new Score();
            boolean parsed;

            try (InputStream stream = new FileInputStream(input)) {
                parsed = Leadsheet.readLeadSheet(new Tokenizer(stream), score);
            }

            if (!parsed) {
                fail(EXIT_FAILURE, "Falha ao interpretar o arquivo .ls.");
            }

            if (score.getPartList().size() == 0) {
                fail(EXIT_FAILURE, "O arquivo .ls nao possui parte melodica.");
            }

            ExportToMusicXMLCommand exporter = new ExportToMusicXMLCommand(
                    output,
                    score,
                    0,
                    Transposition.none);
            exporter.execute();

            if (exporter.getError() != null) {
                fail(EXIT_FAILURE, "Falha ao exportar MusicXML.");
            }

            if (!output.isFile() || output.length() == 0) {
                fail(EXIT_FAILURE, "O arquivo MusicXML nao foi criado.");
            }
        } catch (Throwable throwable) {
            fail(EXIT_FAILURE, "Conversao nao concluida: " + safeMessage(throwable));
        }
    }

    private static void loadVocabulary() throws Exception {
        String vocabularyName = Preferences.getPreference(
                Preferences.DEFAULT_VOCAB_FILE);
        File vocabulary = new File(ImproVisor.getVocabDirectory(), vocabularyName);

        if (!vocabulary.isFile() || !vocabulary.canRead()) {
            throw new IllegalStateException("Vocabulario do Impro-Visor nao encontrado.");
        }

        Polylist rules = Polylist.nil;
        try (InputStream stream = new FileInputStream(vocabulary)) {
            Tokenizer tokenizer = new Tokenizer(stream);
            Object item;
            while ((item = tokenizer.nextSexp()) != Tokenizer.eof) {
                if (item instanceof Polylist && ((Polylist) item).nonEmpty()) {
                    rules = rules.cons(item);
                }
            }
        }

        Advisor advisor = new Advisor();
        advisor.setRules(rules.reverse());
    }

    private static String safeMessage(Throwable throwable) {
        String message = throwable.getMessage();
        return message == null || message.trim().isEmpty()
                ? throwable.getClass().getSimpleName()
                : message;
    }

    private static void fail(int exitCode, String message) {
        System.err.println(message);
        System.exit(exitCode);
    }
}
