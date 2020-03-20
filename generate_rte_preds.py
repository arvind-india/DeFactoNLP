import jsonlines
import json
import doc_retrieval
import sentence_retrieval
import rte.rte as rte
import utilities
import spacy
import os
import codecs
import unicodedata as ud

from allennlp.models.archival import load_archive
from allennlp.predictors import Predictor

relevant_sentences_file = "data/dev_relevant_docs.jsonl"
concatenate_file = "data/dev_concatenation.jsonl"
instances = []
zero_results = 0

relevant_sentences_file = jsonlines.open(relevant_sentences_file)
model = "rte/fever_output/model.tar.gz"
model = load_archive(model)
predictor = Predictor.from_archive(model)

wiki_dir = "data/wiki-pages/wiki-pages"
wiki_split_docs_dir = "../wiki-pages-split"

claim_num = 1

wiki_entities = os.listdir(wiki_split_docs_dir)
for i in range(len(wiki_entities)):
    wiki_entities[i] = wiki_entities[i].replace("-SLH-", "/")
    wiki_entities[i] = wiki_entities[i].replace("_", " ")
    wiki_entities[i] = wiki_entities[i][:-5]
    wiki_entities[i] = wiki_entities[i].replace("-LRB-", "(")
    wiki_entities[i] = wiki_entities[i].replace("-RRB-", ")")

for line in relevant_sentences_file:
    instances.append(line)

nlp = spacy.load('en_core_web_lg')


def create_test_set(claim, candidateEvidences, claim_num):
    testset = []
    for elem in candidateEvidences:
        testset.append({"hypothesis": claim, "premise": elem})
    return testset


def run_rte(claim, evidence, claim_num):
    fname = "claim_" + str(claim_num) + ".json"
    test_set = create_test_set(claim, evidence, claim_num)
    preds = predictor.predict_batch_json(test_set)
    return preds


with jsonlines.open(concatenate_file, mode='w') as writer_c:
    for i in range(len(instances)):
        claim = instances[i]['claim']
        print(claim)
        evidence = instances[i]['predicted_sentences']
        potential_evidence_sentences = []
        # TODO: implement NER to generate file in order to evaluate.
        for sentence in evidence:
            # print(sentence)
            # print(sentence[0])
            # load document from TF-IDF
            relevant_doc = ud.normalize('NFC', sentence[0])
            relevant_doc = relevant_doc.replace("/", "-SLH-")
            file = codecs.open(wiki_split_docs_dir + "/" + relevant_doc + ".json", "r", "utf-8")
            file = json.load(file)
            full_lines = file["lines"]

            lines = []
            for line in full_lines:
                lines.append(line['content'])


            lines[sentence[1]] = lines[sentence[1]].strip()
            lines[sentence[1]] = lines[sentence[1]].replace("-LRB-", " ( ")
            lines[sentence[1]] = lines[sentence[1]].replace("-RRB-", " ) ")

            potential_evidence_sentences.append(lines[sentence[1]])

        # Just adding a check
        # This is needed in case nothing was predicted
        if len(potential_evidence_sentences) == 0:
            zero_results += 1
            potential_evidence_sentences.append("Nothing")
            evidence.append(["Nothing", 0])
        relevant_docs, entities = doc_retrieval.getRelevantDocs(claim, wiki_entities, "spaCy",
                                                                nlp)  # "spaCy", nlp)#
        print(relevant_docs)
        # print(entities)
        relevant_sentences = sentence_retrieval.getRelevantSentences(relevant_docs, entities, wiki_split_docs_dir)
        # print(relevant_sentences)

        predicted_evidence = []
        for sent in relevant_sentences:
            predicted_evidence.append((sent['id'], sent['line_num']))
            potential_evidence_sentences.append(sent['sentence'])
            evidence.append((sent['id'], sent['line_num']))

        instances[i]['predicted_pages_ner'] = relevant_docs
        instances[i]['predicted_sentences_ner'] = predicted_evidence

        writer_c.write(instances[i])
        print("Claim number: " + str(i) + " of " + str(len(instances)))

        preds = run_rte(claim, potential_evidence_sentences, claim_num)

        saveFile = codecs.open("rte/entailment_predictions/claim_" + str(claim_num) + ".json", mode="w+",
                               encoding="utf-8")
        for j in range(len(preds)):
            # print(preds)
            # print(evidence)
            preds[j]['claim'] = claim
            preds[j]['premise_source_doc_id'] = evidence[j][0]
            preds[j]['premise_source_doc_line_num'] = evidence[j][1]
            preds[j]['premise_source_doc_sentence'] = potential_evidence_sentences[j]
            saveFile.write(json.dumps(preds[j], ensure_ascii=False) + "\n")

        saveFile.close()
        claim_num += 1
        # print(claim_num)
        # print(instances[i])

print("Number of Zero Sentences Found: " + str(zero_results))
