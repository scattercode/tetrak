---
title: "Classical spelling, Russian notes and a cursive italic: two releases of the Armenian recogniser"
date: 2026-11-23
draft: false
slug: "classical-spelling-russian-notes-and-a-cursive-italic"
kicker: "Progress"
standfirst: "Much of an Armenian library is printed in a spelling our recogniser had never been shown, and Yerevan's scholarly editions quote Russian it had no letters for. v7 reads both, and v8 reads an italic that v7 could not. One register still goes to another engine by a distance, and finding out why led us to the transcripts we score against"
author: stephen-masters
tags: [armenian, ocr, orthography, training, evaluation, project-notes]
---

In 1991 a press in Beirut printed the memoirs of Alexander Khatisian, who
was mayor of Tiflis before he was prime minister of the first Republic of
Armenia, and who died in exile in Paris. Three years later a press in
Yerevan printed the fifth volume of the complete works of Hovhannes
Tumanyan, his stories and tales. The two men were contemporaries, and the
two books are near neighbours in date. To an OCR model they are different
worlds.

The Yerevan volume is in the spelling adopted in Soviet Armenia in 1922,
and its editors' notes quote Russian. The Beirut one is in the classical
spelling the diaspora never gave up, down to its title: the title page
prints *Քաղաքապետի մը յիշատակները* (Memoirs of a mayor), where Armenian
Wikisource files the book under the reformed *հիշատակները*. It is also
set almost throughout in a heavy cursive italic.

Until this month our Armenian recogniser read the first of those books
well, apart from every Russian word in it, and the second badly. This
article covers the two releases that changed that, v7 and v8, what each
cost, and the register another engine still reads much better than we do.

## Two things the model had never seen

v6, the model we
[wrote about in October]({{< relref "/articles/2026/10/2026-10-02-beating-the-baselines.md" >}}),
led most of the registers we measured it on. Every one of those registers
was in reformed spelling. Two kinds of text that sit on the same shelves
were outside anything it had been trained on.

**Classical spelling.** Everything printed in Armenian before 1922, and
nearly everything the diaspora has printed since, uses the older
orthography. We have written about
[telling the two apart]({{< relref "/articles/2026/10/2026-10-11-classical-or-reformed-armenian-by-one-letter.md" >}}).
The reform was a respelling, and both spellings draw on the same letters,
so nothing here needed a new alphabet. What changes is how often each
letter turns up and where: `ւ` standing on its own and not only inside
`ու`, and `եւ` set as two letters where reformed print sets the ligature
`և`. A recogniser learns those habits along with the shapes, and ours had
learnt the reformed ones. The classical books brought exactly one printed
character the model had no class for, the apostrophe of elision `՚`.

**Russian.** Yerevan's scholarly editions mix Russian into Armenian pages:
bibliographies, titles, quotations in the notes. v6 had no Cyrillic
letters at all, so those words could not be read however well the rest of
the page went, and every training line that contained one had been thrown
away. The Russian arrives as scattered words and short runs inside
Armenian lines, so what has to be learnt is the change of alphabet in the
middle of a line.

The recogniser's output is a fixed list of characters in a fixed order,
and a change to that list is a new model. The trainer already owed its
next run a new list for a handful of symbols, so the next model was going
to be trained from scratch whatever else it did. We put the Russian
alphabet and the classical books into the same run.

## What went into v7

A pre-train on synthetic lines and then a fine-tune on real ones, as
before. Three things were new.

- **Text from every proofread work we harvest from Armenian Wikisource,**
  the classical ones included. The synthetic lines are rendered from it.
  A share of them are in classical spelling, and a small share switch
  between Armenian and Russian within the line.
- **Real crops from the classical books,** cut from the scans and aligned
  with their transcripts, and real crops containing Russian words, which
  earlier harvests had dropped.
- **Nine classical registers, held out before anything was trained,**
  beside the eight we already had. As before, every evaluation page is
  kept out of training, and so is
  [every other page that prints the same text]({{< relref "/articles/2026/10/2026-10-06-when-your-training-set-has-read-your-test-set.md" >}}).

## The dictionary that went backwards

The first fine-tune was better than v6 on every classical register, and
it read Russian for the first time. It was worse on one register, the
Armenian–English dictionary, and our first explanation was wrong.

We assumed lookalikes. Cyrillic and Latin share several shapes (`а` and
`a`, `р` and `p`, `с` and `c`), and a model that has just learnt Cyrillic
might well spell *poor* as *роог*. It did, a handful of times. But when
we went through the English words v6 had read and the new model had not,
nearly all of them were ordinary misreadings in Latin letters: *genlle*
for *gentle*, *Ietter* for *letter*. The cause was in what the pre-train
had been fed. To teach the model Russian we had rendered many times more
lines containing Cyrillic than lines of Latin alone, and its English had
gone unpractised.

Two fixes followed. A fourth synthetic set, English lines from
public-domain novels, went into a second fine-tune, and the dictionary
came back. And the script fold in the library, which already turned a
Latin `h` inside an Armenian word back into `հ`, learnt a third script.
A token with no Armenian letter is now written in whichever of Latin or
Cyrillic its unambiguous letters belong to, and a token made only of
shared shapes follows the text around it. The English set was not free:
it took a little off the classical gain, and we kept it.

## Two word lists, because a spelling is not a mistake

The recogniser has no language model, so since v6 a word list has sat
behind it. A word whose reading is not in the list takes a listed reading
from the recogniser's own alternatives, when one is nearly as probable.
That list was counted from reformed text. Run over a classical page, it
would do what a well-meaning modern proofreader might do, and respell the
page one word at a time.

So there are two lists now: one counted from the reformed books, and one
from the classical books together with the
[Nayiri Armenian Lexicon](http://www.nayiri.com/nayiri-armenian-lexicon).
There is one rule. A word found in either list is accepted as written and
is never rewritten into the other's spelling. `եւ` and `և` count as the
same word. Before shipping the cure we measured the harm we had feared:
on held-out crops from the classical books, the reformed list alone broke
more words than it fixed, and the two lists together fixed many more than
they broke.

## What v7 cost

We had set v7 a gate: no worse than v6 on any of the eight older
registers. It did not meet it. Through the full pipeline, several of the
older registers lost a little word recall.

The same losses, the same size, show in the recogniser's raw output, with
no word lists, no fold and no layout step behind it. We had promised
ourselves a comparison of that kind before publishing, because the run
changed two things at once. It says that the recogniser itself gave up a
little on the reformed registers in order to learn the rest, and that the
post-processing is neither causing the loss nor hiding a larger one.

We shipped v7 on 16 November knowing that. The losses are small and the
classical gains are not, and the
[model card](https://huggingface.co/tetrak/easyocr-armenian) records them
as a known defect. v8 has since recovered some of the ground; a few of
the older registers are still a little below v6.

## The engine we measured last

Calfa's `hye-paddle` is the strongest other Armenian engine we have
measured. The model we run is `paddle-calfa-tiny`, version 1.0.0. Calfa
has since published a larger one in the same repository, which we have
not yet run, so read "`hye-paddle`" below as the smaller model. We have
[published a comparison without it before]({{< relref "/articles/2026/09/2026-09-24-the-engine-we-had-left-out.md" >}}).
We did it again, and not by choice. Its first run over the classical
registers failed on every page within two minutes. A routine dependency
update in Tetrak had quietly resolved the Paddle packages back to a
version that cannot load Calfa's model. v7's model card went up with a
comparison against the other three engines, and by that comparison v7 led
nearly all of the classical registers.

That evening, with the dependency pinned, `hye-paddle` ran. v7 kept the
lead on mean word recall, but `hye-paddle` took several of the classical
registers from it, two of them by a wide margin. We corrected the card
the same night.

The two were Khatisian's memoirs and the first volume of Khachatur
Abovyan's complete works, a Yerevan edition of 1948. They turned out to fail for different reasons,
and neither was the reason we would have guessed.

## Khatisian: a typeface the harvester could not see

Nine of Khatisian's ten evaluation pages are set in the cursive italic
and one is in upright type. The upright page was the only one of the ten on which
v7 beat `hye-paddle`.

We ruled out the scan first. Thinning the strokes, blurring the pages and
lowering their resolution left recall the same or worse. We ruled out
vocabulary: fewer of this book's words fall outside the word lists than
any other classical register's. What was left was the cut of the type.
The errors were of a kind no other register shows: `ռ` read as `ո`, and
`ւ`, which this italic draws as a small tick, read as a colon.

The model had barely seen the face, and the reason is built into how we
collect training data. Real crops come from running the current model
over a scanned page and keeping the lines whose reading can be aligned
with the transcript. A typeface the current model reads badly aligns
badly, so it contributes few crops, so the next model reads it badly too.
Khatisian's book had supplied a fraction of one per cent of v7's real
crops. Italic as a style was not the problem: v7 read the italics we
render with exactly as well as the upright faces. It was this older
cursive cut, which the diaspora presses used and none of our typefaces
imitates.

The loop does loosen with each model. v7 could align far more of the book
than v6 could, so we harvested every proofread page of it with v7 and got
many times the crops. v8 is v7 fine-tuned with a share of each batch
given to those crops and to crops from two other books set in italics.

Beside it we trained a control: the same number of extra iterations on
v7's own recipe, with no new material. The control barely moved, so the
gain belongs to the crops and not to the extra training. We had learnt to
want that a few hours earlier, from a first attempt that changed several
things at once. It gained on Khatisian, lost on two other registers, and
could not say which change was to blame. The run we shipped changes one
thing.

v8 went out on 18 November. Its price is in the Russian. The italic books
contain almost none, and v8 reads a few fewer of the Russian words in
Tumanyan's notes than v7 did. We published knowing that as well, and the
model card gives the count.

## Abovyan: a photograph, and then a transcript

The Abovyan pages are verse in Grabar, the classical language itself, set
in a light italic. The recogniser copes with the face. What marks the
book out is the photography: its ink is pale grey on grey paper, where
every other book we hold at that resolution is black on white.

Stretching the contrast before reading helped at once, and that became a
rule in the pipeline, measured on every register before it shipped. A
page whose darkest ink is still pale is stretched to full contrast before
detection, and every other page reaches the detector untouched. The rule
looks at the ink and not at the paper, because one register of black ink
on toned paper read slightly worse when stretched. The
[engines page]({{< relref "/ocr/reference/engines.md#armenian-with-our-own-recogniser" >}})
has the threshold.

That closed part of the gap. To close the rest we did the obvious thing
and harvested the rest of the edition: several times the Abovyan crops,
some of them stretched exactly as the pipeline stretches a page. It did
nothing. The fine-tune with all the new material moved the register no
further than a control with none of it.

So we asked a question we should have asked earlier: are the transcripts
right? The pages are marked as proofread on Wikisource, which means one
contributor has read the page against the scan. On one of the
worst-scoring pages we took every word where our model and `hye-paddle`
read the same thing and the transcript said another, and checked each
against the scan. The two engines are built on different architectures
by different people, so when they agree against the transcript it is
worth looking. Every one of those words was an error in the transcript.
Reading
the rest of the page line by line found more, about one word in seven in
all. The scanned file carries a text layer from some earlier OCR, and the
transcript had that layer's mistakes word for word.

We corrected the page on Wikisource against the scan, as any proofreader
there would, and scored it again. Both engines went up. The gap between
them did not close, so the bad transcript had been hiding a real
difference and not manufacturing one. Most of what remains sits in a few
pages that are out of focus as well as faint, and blur is not something
more crops of the same typeface will teach.

Two changes to the trainer came out of it.

- **A screen before the harvest.** The harvester now checks a page before
  cutting crops from it. A word is suspect when our reading and stock
  Tesseract's agree with each other against the transcript and the word
  lists do not explain the disagreement away, and a page with too many
  suspect words gives no crops. A bad transcript does its damage exactly
  where a crop is most useful: a harvested crop teaches the model
  something only where the model disagreed with its label, and those are
  the labels most likely to be the typos.
- **Our own cleaning.** Our clean-up of the transcripts had been
  dropping any text wrapped in a formatting template, such as a centred
  heading. That is fixed.

The tables below still score Abovyan against the uncorrected page, and
its other nine pages have not been checked. We will regenerate the row
when the register has been read through.

{{< registers >}}

{{< registers metric="chr" >}}

## Where we still lose, and why

v8 leads both means, and most registers by word recall. The bilingual
dictionary flatters our mean, because Calfa's models are Armenian-only
and read its English badly; without that register the lead on the mean
narrows and stays. Where we do not lead:

- **Abovyan.** Both of Calfa's models read it better, `hye-paddle` by a
  distance. These are faint, partly out-of-focus photographs of Grabar
  verse, scored against transcripts we now know to be unreliable. More
  training data of the same kind does not help. We have tried.
- **Khatisian.** Most of the gap has gone and a little is left. We have
  not found a typeface in that older cursive cut that we are free to
  render with, so the model's only examples are the book's own pages.
- **Aghbalyan's criticism.** `hye-paddle` is a little ahead, and we have
  not yet studied why.
- **Faustus of Byzantium.** As in October: the index and notes are set in
  a bold italic whose digits the recogniser confuses.
- **Character similarity** is more mixed than word recall, as the second
  table shows. On the medical encyclopedia the cause is the one we
  described in October: the detector draws no box around the dash its
  index prints, so no recogniser behind it can read one.
- **Russian.** v8 reads most of the Russian words on the Tumanyan pages,
  and fewer than v7.
- **Mshak.** We have begun transcribing pages of an 1870s newspaper, the
  first evaluation material that does not come from Wikisource. On the
  two pages done so far `hye-paddle` is well ahead. Two pages are too few
  to put in a table.

Calfa's two models are licensed CC BY-NC 4.0, so we can measure them and
nobody can ship them in a commercial pipeline. Ours can be shipped: the
code and weights are Apache 2.0, and the word lists are CC BY-SA 4.0, as
the sources they are counted from require. That difference is a reason to
keep building ours. It is not a reason to describe theirs as anything but
the better reader of those books.

## What we would tell ourselves a month ago

**Run every engine before writing the claim.** We knew this, and wrote it
down in September. The claim on v7's card stood for less than a day, and
only because we went back that evening.

**A harvest made with your own model inherits its blind spots.** A source
that yields few crops is not a small source. It is a source the model
cannot read, which is the one that most needs crops. We now look at yield
by source before deciding what a run is missing.

**Change one thing and train a control beside it.** The run that changed
several things cost a night and answered nothing. The control costs the
same hours every time. Once it told us a gain was real, and once that a
gain we were pleased with was only more training.

**When more data does nothing, check the labels.** Two unrelated engines
agreeing against the ground truth is cheap to compute. On the one page
where we checked every case by eye, it was right every time.

## Further reading

### How the recogniser works

- Baoguang Shi, Xiang Bai and Cong Yao, "An end-to-end trainable neural
  network for image-based sequence recognition and its application to
  scene text recognition", *IEEE Transactions on Pattern Analysis and
  Machine Intelligence* 39(11), 2017, pp. 2298–2304.
  [doi:10.1109/TPAMI.2016.2646371](https://doi.org/10.1109/TPAMI.2016.2646371).
  The CRNN: convolutional features, a recurrent layer and a CTC output.
  EasyOCR's recognition network is one, and ours keeps its architecture.
- Alex Graves, Santiago Fernández, Faustino Gomez and Jürgen Schmidhuber,
  "Connectionist temporal classification: labelling unsegmented sequence
  data with recurrent neural networks", *Proceedings of the 23rd
  International Conference on Machine Learning*, 2006, pp. 369–376.
  [doi:10.1145/1143844.1143891](https://doi.org/10.1145/1143844.1143891).
  The output layer. It explains two things in this article: why the list
  of characters is fixed when training starts, and why the recogniser
  has no knowledge of words, which is what the word lists supply.
- Jeonghun Baek, Geewook Kim, Junyeop Lee, Sungrae Park, Dongyoon Han,
  Sangdoo Yun, Seong Joon Oh and Hwalsuk Lee, "What is wrong with scene
  text recognition model comparisons? Dataset and model analysis",
  *IEEE/CVF International Conference on Computer Vision (ICCV)*, 2019,
  pp. 4714–4722.
  [doi:10.1109/ICCV.2019.00481](https://doi.org/10.1109/ICCV.2019.00481).
  EasyOCR's training pipeline is a modified version of this paper's
  framework. Its argument, that recognisers are routinely compared on
  inconsistent data, is the one we keep relearning.
- Youngmin Baek, Bado Lee, Dongyoon Han, Sangdoo Yun and Hwalsuk Lee,
  "Character region awareness for text detection", *IEEE/CVF Conference
  on Computer Vision and Pattern Recognition (CVPR)*, 2019,
  pp. 9357–9366.
  [doi:10.1109/CVPR.2019.00959](https://doi.org/10.1109/CVPR.2019.00959).
  CRAFT, the detector that finds the lines before any recogniser reads
  them. We use it unchanged, which is why a faint page has to be
  stretched before it and not after.

### Ground truth and scan quality

- Curtis G. Northcutt, Anish Athalye and Jonas Mueller, "Pervasive label
  errors in test sets destabilize machine learning benchmarks",
  *Proceedings of the Neural Information Processing Systems Track on
  Datasets and Benchmarks* 1, 2021.
  [arXiv:2103.14749](https://arxiv.org/abs/2103.14749). Label errors in
  the test sets of ten widely used benchmarks, found by a method close in
  spirit to ours: look where confident models disagree with the label.
  It also shows that such errors can change which model appears to win.
- Rose Holley, "How good can it get? Analysing and improving OCR accuracy
  in large scale historic newspaper digitisation programs", *D-Lib
  Magazine* 15(3/4), 2009.
  [doi:10.1045/march2009-holley](https://doi.org/10.1045/march2009-holley).
  An account from the Australian Newspaper Digitisation Program of what
  limits OCR accuracy on historical print, stage by stage from the source
  to the software. The Abovyan register is a reminder of how much is
  decided before any engine runs.
- English Wikisource,
  [Help:Page status](https://en.wikisource.org/wiki/Help:Page_status), and
  MediaWiki,
  [the ProofreadPage page quality system](https://www.mediawiki.org/wiki/Help:Extension:ProofreadPage/Page_quality_system).
  What the statuses on a Wikisource page mean. "Proofread" is one
  contributor's reading against the scan; "validated" needs a second
  person. Many of the pages we train on are at the first level.

### Armenian print, spelling and the other engines

- Irina Marchesini, "Russian (1917–1918) and Armenian (1922) orthographic
  reforms. Assessing the Russian influence on Modern Armenian language",
  *Studi Slavistici* 14(1), 2017, pp. 171–190.
  [doi:10.13128/Studi_Slavis-21944](https://doi.org/10.13128/Studi_Slavis-21944).
  Open access. The reform that divides the two spellings, from 1922 to
  the revision of 1940.
- Unicode Consortium, *The Unicode Standard, Version 18.0*, chapter 7,
  [section 7.6, "Armenian"](https://www.unicode.org/versions/Unicode18.0.0/core-spec/chapter-7/#G3334).
  The script as encoded, including the two characters this article turns
  on: U+055A ARMENIAN APOSTROPHE, the one character the classical books
  added, and U+0587 ARMENIAN SMALL LIGATURE ECH YIWN, the `և` that
  classical print sets as two letters.
- Chahan Vidal-Gorène, Nadi Tomeh and Victoria Khurshudyan,
  "Semantic-guided reading order reconstruction in historical Armenian
  newspapers with LLMs", preprint, 2026.
  [arXiv:2607.00596](https://arxiv.org/abs/2607.00596). From the team
  behind the Calfa models we measure against, and the paper that releases
  their Tesseract model for historical Armenian print.
- Chahan Vidal-Gorène, Aliénor Decours-Perez, Baptiste Queuche, Agnès
  Ouzounian and Thomas Riccioli, "Digitalization and enrichment of the
  Նոր Բառգիրք Հայկազեան Լեզուի: work in progress for Armenian
  lexicography", *Journal of the Society for Armenian Studies* 27(2),
  2021, pp. 224–244.
  [doi:10.1163/26670038-12342714](https://doi.org/10.1163/26670038-12342714).
  Character recognition of a printed Classical Armenian dictionary of
  1836–37, by the same team.
- Calfa, [hye-paddle](https://huggingface.co/calfa-ai/hye-paddle) and
  [hye-tesseract](https://huggingface.co/calfa-ai/hye-tesseract) on
  Hugging Face. The two models compared here, with their cards. Both are
  CC BY-NC 4.0.
