import imp.ImproVisor;
import imp.com.ExportToMusicXMLCommand;
import imp.data.Leadsheet;
import imp.data.ChordPart;
import imp.data.MelodyPart;
import imp.data.Score;
import imp.data.Transposition;
import imp.data.advice.Advisor;
import imp.guidetone.GuideLineGenerator;
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
    private static final String GUIDE_TONES_OPERATION = "guidetones";

    private ImproVisorBridge() {
    }

    public static void main(String[] args) {
        boolean generateGuideTones = args.length == 3
                && GUIDE_TONES_OPERATION.equals(args[0]);
        boolean convertLeadsheet = args.length == 2;

        if (!generateGuideTones && !convertLeadsheet) {
            fail(EXIT_USAGE,
                    "Uso: ImproVisorBridge <input.ls> <output.xml>"
                    + " | ImproVisorBridge guidetones <input.ls> <output.xml>");
        }

        if (!Boolean.parseBoolean(System.getProperty("java.awt.headless"))) {
            fail(EXIT_USAGE, "Execute com -Djava.awt.headless=true.");
        }

        int pathArgumentOffset = generateGuideTones ? 1 : 0;
        File input = new File(args[pathArgumentOffset]);
        File output = new File(args[pathArgumentOffset + 1]);

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

            if (generateGuideTones) {
                replaceMelodyWithGuideTones(score);
            } else if (score.getPartList().size() == 0) {
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

    private static void replaceMelodyWithGuideTones(Score score) {
        ChordPart chords = score.getChordProg();
        if (chords == null || chords.getChords().isEmpty() || chords.size() == 0) {
            fail(EXIT_FAILURE, "O arquivo .ls nao possui progressao harmonica.");
        }

        GuideLineGenerator generator = new GuideLineGenerator(
                chords,
                GuideLineGenerator.NOPREFERENCE,
                "3",
                "",
                true,
                55,
                79,
                0,
                false,
                false,
                true,
                "");
        MelodyPart guideTones = generator.makeGuideLine();

        if (guideTones == null || guideTones.size() == 0) {
            fail(EXIT_FAILURE, "O Impro-Visor nao gerou guide tones.");
        }
        if (guideTones.size() != chords.size()) {
            fail(EXIT_FAILURE, "A duracao dos guide tones nao corresponde a harmonia.");
        }

        int melodyPartCount = score.getPartList().size();
        score.clearParts();
        for (int index = 0; index < melodyPartCount; index++) {
            score.delPart(0);
        }
        score.addPart(guideTones);
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
