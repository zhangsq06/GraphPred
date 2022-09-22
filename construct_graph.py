import scipy.sparse
# from utils import *
from load_data import load_encode_test, load_encode_train
import numpy as np
import time
from scipy.spatial import distance
import argparse
##########
parser = argparse.ArgumentParser(description="Process ATAC-seq data.")
parser.add_argument('--dataset', default='GSE11420x_encode',type=str,help='The prefix name of the dataset')
parser.add_argument('--k', default=5,type=int,help='The length of k-mer')
args = parser.parse_args()
######load label###############
def load_labels(seqs):
    n = len(seqs)
    labels = [seq[1] for seq in seqs]
    seqs = [seq[0] for seq in seqs]
    labels_t = []
    for label in labels:
        if label == 0.0:
            labels_t.append(0.0)
        else:
            labels_t.append(1.0)
    labels = np.reshape(np.array(labels_t), [n, 1])
    return labels
# ##############################
def construct_vocab(seqs, size, thresh = 3):#
    word_vocab = {}
    word_freq = {}
    n_sqs = len(seqs)
    for i, seq in enumerate(seqs):
        subseqs = [seq[t:t+size] for t in range(0, len(seq) - size+1, 1)]
        word_vocab[seq]=subseqs
        for subseq in subseqs:
            if subseq not in list(word_freq.keys()):
                word_freq[subseq] = 1
            else:
                word_freq[subseq]+=1
    return word_vocab,word_freq
def kmer_seq(word_vocab,word_freq,seqs):
    keys=list(word_freq.keys())#KMERS
    keys_seqs={}
    for kmer in keys:
        kseqs = [seq for seq  in seqs if kmer in word_vocab[seq]]
        keys_seqs[kmer]=kseqs
    return keys_seqs
#################################

###jisuan 
def tf_ks(seq,size=5):
    sword_freq = {}
    for i in range(0,len(seq)-size+1,1):
        subseq = seq[i:i+size]
        if subseq not in sword_freq:
            sword_freq[subseq] = 1
        else:
            sword_freq[subseq]+=1
    return sword_freq
#####################################
def standardization(data):
	data = np.array(data)
	mu = np.mean(data, axis=0)
	sigma = np.std(data, axis=0)
	nor_data = (data-mu)/sigma 
	nor_data = list(nor_data)
	return nor_data
##########################inclusive edge####################
def inclusive_edge(word_vocab,word_freq,seqs,size):    
    k_mers=list(word_freq.keys())
    N=len(seqs)
    kmer_vocab={}
    for kmers in k_mers:
        dfk=0    
        for seq in seqs:
            if kmers in word_vocab[seq]:
                dfk +=1
        kmer_vocab[kmers]=dfk
    rows=[]
    cols=[]
    weights=[]

    for i in range(len(k_mers)):
        kmers= k_mers[i]  
        for j in range(len(seqs)):
            seq=seqs[j]
            if kmers in word_vocab[seq]:
                tfks=tf_ks(seq,size)
                tfks=tfks[kmers]
                Ainclu_ks=tfks*np.log(N/kmer_vocab[kmers])
            else:
                Ainclu_ks=0
            weights.append(Ainclu_ks)
            rows.append(j)
            cols.append(i)
    weights = standardization(weights) #
    adj = scipy.sparse.csr_matrix((weights, (rows, cols)),shape=(len(seqs),len(k_mers)))        
    return adj
#####################similarity edge#######################
def Asim(seqs,word_freq):
    rows=[]
    cols=[]
    weights=[]
    keys=list(word_freq.keys())
    for i in range(len(keys)):
        for j in range(len(keys)):
            if i<=j:
                weight=distance.hamming(list(keys[i]), list(keys[j]))
                weights.append(weight)
                rows.append(i)
                cols.append(j)
    node_size = len(keys)
    weights = standardization(weights) #
    adj = scipy.sparse.csr_matrix((weights, (rows, cols)),shape=(node_size, node_size))
    Asim = adj + adj.T.multiply(adj.T > adj) - adj.multiply(adj.T > adj)
    return Asim
###################co-occurrence edge######################
def Acoo_value(seqs,K12,K1,K2):    
    if K12>0:
        pk1k2 = K12/len(seqs)
        pk1 = (K1+K12)/len(seqs)
        pk2 = (K2+K12)/len(seqs)
        Acoo_k1k2 = np.log(pk1k2/(pk1*pk2+1e-3))
    else:
        Acoo_k1k2 = 0
    weight = Acoo_k1k2

    return weight
def Acoo(seqs,word_freq,word_vocab):
    keys=list(word_freq.keys())#KMERS
    rows_cols = [[i,j] for i in range(len(keys)) for j in range(i, len(keys))]
    kmers = [[keys[i],keys[j]] for i in range(len(keys)) for j in range(i, len(keys))]
    rows=np.random.rand(len(kmers))
    cols=np.random.rand(len(kmers))
    weights=np.random.rand(len(kmers))
    kmer_seqs = kmer_seq(word_vocab,word_freq,seqs)
    for t in range(len(kmers)):
        K12 = len(set(kmer_seqs[kmers[t][0]]) & set(kmer_seqs[kmers[t][1]]))
        if K12>0:
            K1 = len(set(kmer_seqs[kmers[t][0]]))
            K2 = len(set(kmer_seqs[kmers[t][1]]))
            weight = Acoo_value(seqs,K12,K1,K2)
        else:
            weight = 0
        weights[t] = weight
        rows[t]= rows_cols[t][0]
        cols[t] = rows_cols[t][1]

    node_size = len(keys)
    weights = standardization(weights) #
    adj = scipy.sparse.csr_matrix((weights, (list(rows), list(cols))),shape=(node_size, node_size))
    # adj = adj.T+adj
    Acoo = adj + adj.T.multiply(adj.T > adj) - adj.multiply(adj.T > adj)
    return Acoo
#################calculate the inclusive, coexisting and similarity matrices############################
def generateAdjs(tfid,Kmers=5):
    test_seqs = load_encode_test(tfid)
    train_seqs = load_encode_train(tfid)
    ###AC+B
    seqs = train_seqs + test_seqs
    labels = load_labels(seqs)
    seqs = [seq[0] for seq in seqs]
    word_vocab,word_freq=construct_vocab(seqs, size=Kmers)
    adj_inclu = inclusive_edge(word_vocab,word_freq,seqs,size=Kmers)
    adj_sim = Asim(seqs,word_freq)
    
    adj_coo = Acoo(seqs,word_freq,word_vocab)
    return adj_inclu, adj_sim,adj_coo, labels

if __name__=='__main__':    
    start_time=time.time()
    adj_inclu, adj_sim,adj_coo, labels= generateAdjs(args.dataset,Kmers=5)
    end_time=time.time()
    total_time=np.array(end_time-start_time)
    print(adj_inclu.toarray().shape, adj_sim.toarray().shape, adj_coo.toarray().shape,len(labels))
    print('total_time:',total_time)




